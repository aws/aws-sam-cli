"""
Provides methods to generate and send metrics
"""
import logging
import platform
import uuid
from dataclasses import dataclass
from functools import reduce, wraps
from pathlib import Path
from timeit import default_timer
from typing import Any, Dict, Optional

import click

from samcli import __version__ as samcli_version
from samcli.cli.context import Context
from samcli.cli.global_config import GlobalConfig
from samcli.commands._utils.experimental import get_all_experimental_statues
from samcli.commands.exceptions import UnhandledException, UserException
from samcli.lib.hook.exceptions import InvalidHookPackageConfigException
from samcli.lib.hook.hook_config import HookPackageConfig
from samcli.lib.hook.hook_wrapper import INTERNAL_PACKAGES_ROOT
from samcli.lib.hook.utils import get_hook_metadata
from samcli.lib.iac.cdk.utils import is_cdk_project
from samcli.lib.iac.plugins_interfaces import ProjectTypes
from samcli.lib.telemetry.cicd import CICDDetector, CICDPlatform
from samcli.lib.telemetry.event import EventTracker
from samcli.lib.telemetry.project_metadata import get_git_remote_origin_url, get_initial_commit_hash, get_project_name
from samcli.lib.telemetry.telemetry import Telemetry
from samcli.lib.telemetry.user_agent import get_user_agent_string
from samcli.lib.warnings.sam_cli_warning import TemplateWarningsChecker

LOG = logging.getLogger(__name__)

WARNING_ANNOUNCEMENT = "WARNING: {}"

"""
Global variables are evil but this is a justified usage.
This creates a versatile telemetry tracking no matter where in the code. Something like a Logger.
No side effect will result in this as it is write-only for code outside of telemetry.
Decorators should be used to minimize logic involving telemetry.
"""
_METRICS = dict()


@dataclass
class ProjectDetails:
    project_type: str
    hook_name: Optional[str]
    hook_package_version: Optional[str]


def send_installed_metric():
    LOG.debug("Sending Installed Metric")

    telemetry = Telemetry()
    metric = Metric("installed")
    metric.add_data("osPlatform", platform.system())
    metric.add_data("telemetryEnabled", bool(GlobalConfig().telemetry_enabled))
    telemetry.emit(metric, force_emit=True)


def track_template_warnings(warning_names):
    """
    Decorator to track when a warning is emitted. This method accepts name of warning and executes the function,
    gathers all relevant metrics, reports the metrics and returns.

    On your warning check method use as follows

        @track_warning(['Warning1', 'Warning2'])
        def check():
            return True, 'Warning applicable'
    """

    def decorator(func):
        """
        Actual decorator method with warning names
        """

        def wrapped(*args, **kwargs):
            telemetry = Telemetry()
            template_warning_checker = TemplateWarningsChecker()
            ctx = Context.get_current_context()

            try:
                ctx.template_dict
            except AttributeError:
                LOG.debug("Ignoring warning check as template is not provided in context.")
                return func(*args, **kwargs)
            for warning_name in warning_names:
                warning_message = template_warning_checker.check_template_for_warning(warning_name, ctx.template_dict)
                metric = Metric("templateWarning")
                metric.add_data("awsProfileProvided", bool(ctx.profile))
                metric.add_data("debugFlagProvided", bool(ctx.debug))
                metric.add_data("region", ctx.region or "")
                metric.add_data("warningName", warning_name)
                metric.add_data("warningCount", 1 if warning_message else 0)  # 1-True or 0-False
                telemetry.emit(metric)

                if warning_message:
                    click.secho(WARNING_ANNOUNCEMENT.format(warning_message), fg="yellow")

            return func(*args, **kwargs)

        return wrapped

    return decorator


def track_command(func):
    """
    Decorator to track execution of a command. This method executes the function, gathers all relevant metrics,
    reports the metrics and returns.

    If you have a Click command, you can track as follows:

    .. code:: python
        @click.command(...)
        @click.options(...)
        @track_command
        def hello_command():
            print('hello')

    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        exception = None
        return_value = None
        exit_reason = "success"
        exit_code = 0

        duration_fn = _timer()

        ctx = None
        try:
            # we have get_current_context in it's own try/except to catch the RuntimeError for this and not func()
            ctx = Context.get_current_context()
        except RuntimeError:
            LOG.debug("Unable to find Click Context for getting session_id.")

        try:
            if ctx and ctx.exception:
                # re-raise here to handle exception captured in context and not run func()
                raise ctx.exception

            # Execute the function and capture return value. This is returned by the wrapper
            # First argument of all commands should be the Context
            return_value = func(*args, **kwargs)
        except (
            UserException,
            click.Abort,
            click.BadOptionUsage,
            click.BadArgumentUsage,
            click.BadParameter,
            click.UsageError,
        ) as ex:
            # Capture exception information and re-raise it later,
            # so metrics can be sent.
            exception = ex
            # NOTE(sriram-mv): Set exit code to 1 if deemed to be user fixable error.
            exit_code = 1
            if hasattr(ex, "wrapped_from") and ex.wrapped_from:
                exit_reason = ex.wrapped_from
            else:
                exit_reason = type(ex).__name__
        except Exception as ex:
            command = ctx.command_path if ctx else ""
            exception = UnhandledException(command, ex)
            # Standard Unix practice to return exit code 255 on fatal/unhandled exit.
            exit_code = 255
            exit_reason = type(ex).__name__

        if ctx:
            time = duration_fn()

            try:
                # metrics also contain a call to Context.get_current_context, catch RuntimeError
                _send_command_run_metrics(ctx, time, exit_reason, exit_code, **kwargs)
            except RuntimeError:
                LOG.debug("Unable to find Click context when sending metrics to telemetry")

        if exception:
            raise exception  # pylint: disable=raising-bad-type

        return return_value

    return wrapped


def _send_command_run_metrics(ctx: Context, duration: int, exit_reason: str, exit_code: int, **kwargs) -> None:
    """
    Emits metrics based on the results of a command run

    Parameters
    ----------
    ctx: Context
        The click context containing parameters, options, etc
    duration: int
        The total run time of the command in milliseconds
    exit_reason: str
        The exit reason from the command, "success" if successful, otherwise name of exception
    exit_code: int
        The exit code of command run
    """
    telemetry = Telemetry()

    # get_all_experimental_statues() returns Dict[str, bool]
    # since we append other values here (not just bool), need to explicitly set type
    metric_specific_attributes: Dict[str, Any] = get_all_experimental_statues() if ctx.experimental else {}

    try:
        template_dict = ctx.template_dict
        project_details = _get_project_details(kwargs.get("hook_name", ""), template_dict)
        if project_details.project_type == ProjectTypes.CDK.value:
            EventTracker.track_event("UsedFeature", "CDK")
        metric_specific_attributes["projectType"] = project_details.project_type
        if project_details.hook_name:
            metric_specific_attributes["hookPackageId"] = project_details.hook_name
        if project_details.hook_package_version:
            metric_specific_attributes["hookPackageVersion"] = project_details.hook_package_version
    except AttributeError:
        LOG.debug("Template is not provided in context, skip adding project type metric")

    metric_name = "commandRunExperimental" if ctx.experimental else "commandRun"
    metric = Metric(metric_name)
    metric.add_data("awsProfileProvided", bool(ctx.profile))
    metric.add_data("debugFlagProvided", bool(ctx.debug))
    metric.add_data("region", ctx.region or "")
    metric.add_data("commandName", ctx.command_path)  # Full command path. ex: sam local start-api

    if not ctx.command_path.endswith("init") or ctx.command_path.endswith("pipeline init"):
        # Project metadata
        # We don't capture below usage attributes for sam init as the command is not run inside a project
        metric_specific_attributes["gitOrigin"] = get_git_remote_origin_url()
        metric_specific_attributes["projectName"] = get_project_name()
        metric_specific_attributes["initialCommit"] = get_initial_commit_hash()

    metric.add_data("metricSpecificAttributes", metric_specific_attributes)
    # Metric about command's execution characteristics
    metric.add_data("duration", duration)
    metric.add_data("exitReason", exit_reason)
    metric.add_data("exitCode", exit_code)
    EventTracker.send_events()  # Sends Event metrics to Telemetry before commandRun metrics
    telemetry.emit(metric)


def _get_project_details(hook_name: str, template_dict: Dict) -> ProjectDetails:
    if not hook_name:
        hook_metadata = get_hook_metadata(template_dict)
        if not hook_metadata:
            project_type = ProjectTypes.CDK.value if is_cdk_project(template_dict) else ProjectTypes.CFN.value
            return ProjectDetails(project_type=project_type, hook_name=None, hook_package_version=None)
        hook_name = str(hook_metadata.get("HookName"))
    hook_location = Path(INTERNAL_PACKAGES_ROOT, hook_name)
    try:
        hook_package_config = HookPackageConfig(package_dir=hook_location)
    except InvalidHookPackageConfigException:
        return ProjectDetails(project_type=hook_name, hook_name=hook_name, hook_package_version=None)
    return ProjectDetails(
        project_type=hook_package_config.iac_framework,
        hook_name=hook_package_config.name,
        hook_package_version=hook_package_config.version,
    )


def _timer():
    """
    Timer to measure the elapsed time between two calls in milliseconds. When you first call this method,
    we will automatically start the timer. The return value is another method that, when called, will end the timer
    and return the duration between the two calls.

    ..code:
    >>> import time
    >>> duration_fn = _timer()
    >>> time.sleep(5)  # Say, you sleep for 5 seconds in between calls
    >>> duration_ms = duration_fn()
    >>> print(duration_ms)
        5010

    Returns
    -------
    function
        Call this method to end the timer and return duration in milliseconds

    """
    start = default_timer()

    def end():
        # time might go backwards in rare scenarios, hence the 'max'
        return int(max(default_timer() - start, 0) * 1000)  # milliseconds

    return end


def _parse_attr(obj, name):
    """
    Get attribute from an object.
    @param obj Object
    @param name Attribute name to get from the object.
        Can be nested with "." in between.
        For example: config.random_field.value
    """
    return reduce(getattr, name.split("."), obj)


def capture_parameter(metric_name, key, parameter_identifier, parameter_nested_identifier=None, as_list=False):
    """
    Decorator for capturing one parameter of the function.

    :param metric_name Name of the metric
    :param key Key for storing the captured parameter
    :param parameter_identifier Either a string for named parameter or int for positional parameter.
        "self" can be accessed with 0.
    :param parameter_nested_identifier If specified, the attribute pointed by this parameter will be stored instead.
        Can be in nested format such as config.random_field.value.
    :param as_list Default to False. Setting to True will append the captured parameter into
        a list instead of overriding the previous one.
    """

    def wrap(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            return_value = func(*args, **kwargs)
            if isinstance(parameter_identifier, int):
                parameter = args[parameter_identifier]
            elif isinstance(parameter_identifier, str):
                parameter = kwargs[parameter_identifier]
            else:
                return return_value

            if parameter_nested_identifier:
                parameter = _parse_attr(parameter, parameter_nested_identifier)

            if as_list:
                add_metric_list_data(metric_name, key, parameter)
            else:
                add_metric_data(metric_name, key, parameter)
            return return_value

        return wrapped_func

    return wrap


def capture_return_value(metric_name, key, as_list=False):
    """
    Decorator for capturing the return value of the function.

    :param metric_name Name of the metric
    :param key Key for storing the captured parameter
    :param as_list Default to False. Setting to True will append the captured parameter into
        a list instead of overriding the previous one.
    """

    def wrap(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            return_value = func(*args, **kwargs)
            if as_list:
                add_metric_list_data(metric_name, key, return_value)
            else:
                add_metric_data(metric_name, key, return_value)
            return return_value

        return wrapped_func

    return wrap


def add_metric_data(metric_name, key, value):
    _get_metric(metric_name).add_data(key, value)


def add_metric_list_data(metric_name, key, value):
    _get_metric(metric_name).add_list_data(key, value)


def _get_metric(metric_name):
    if metric_name not in _METRICS:
        _METRICS[metric_name] = Metric(metric_name)
    return _METRICS[metric_name]


def emit_metric(metric_name):
    if metric_name not in _METRICS:
        return
    telemetry = Telemetry()
    telemetry.emit(_get_metric(metric_name))
    _METRICS.pop(metric_name)


def emit_all_metrics():
    for key in list(_METRICS):
        emit_metric(key)


class Metric:
    """
    Metric class to store metric data and adding common attributes
    """

    def __init__(self, metric_name, should_add_common_attributes=True):
        self._data = dict()
        self._metric_name = metric_name
        self._gc = GlobalConfig()
        self._session_id = self._default_session_id()
        self._cicd_detector = CICDDetector()
        if not self._session_id:
            self._session_id = ""
        if should_add_common_attributes:
            self._add_common_metric_attributes()

    def add_list_data(self, key, value):
        if key not in self._data:
            self._data[key] = list()

        if not isinstance(self._data[key], list):
            # raise MetricDataNotList()
            return

        self._data[key].append(value)

    def add_data(self, key, value):
        self._data[key] = value

    def get_data(self):
        return self._data

    def get_metric_name(self):
        return self._metric_name

    def _add_common_metric_attributes(self):
        self._data["requestId"] = str(uuid.uuid4())
        self._data["installationId"] = self._gc.installation_id
        self._data["sessionId"] = self._session_id
        self._data["executionEnvironment"] = self._get_execution_environment()
        self._data["ci"] = bool(self._cicd_detector.platform())
        self._data["pyversion"] = platform.python_version()
        self._data["samcliVersion"] = samcli_version

        user_agent = get_user_agent_string()
        if user_agent:
            self._data["userAgent"] = user_agent

    @staticmethod
    def _default_session_id() -> Optional[str]:
        """
        Get the default SessionId from Click Context.
        Fail silently if Context does not exist.
        """
        try:
            ctx = Context.get_current_context()
            if ctx:
                return ctx.session_id
            return None
        except RuntimeError:
            LOG.debug("Unable to find Click Context for getting session_id.")
            return None

    def _get_execution_environment(self) -> str:
        """
        Returns the environment in which SAM CLI is running. Possible options are:

        CLI (default)               - SAM CLI was executed from terminal or a script.
        other CICD platform name    - SAM CLI was executed in CICD

        Returns
        -------
        str
            Name of the environment where SAM CLI is executed in.
        """
        cicd_platform: Optional[CICDPlatform] = self._cicd_detector.platform()
        if cicd_platform:
            return cicd_platform.name
        return "CLI"


class MetricDataNotList(Exception):
    pass
