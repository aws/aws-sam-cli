"""
Provides methods to generate and send metrics
"""
import logging
import platform
import uuid
from collections import defaultdict
from collections.abc import MutableMapping
from enum import Enum
from timeit import default_timer
from typing import Any, Dict, Iterator, Optional

import click
from samcli import __version__ as samcli_version
from samcli.cli.context import Context
from samcli.cli.global_config import GlobalConfig
from samcli.commands.exceptions import UserException
from samcli.lib.telemetry.cicd import CICDDetector, CICDPlatform
from samcli.lib.warnings.sam_cli_warning import TemplateWarningsChecker

from .telemetry import Telemetry

LOG = logging.getLogger(__name__)

WARNING_ANNOUNCEMENT = "WARNING: {}"

"""
Global variables are evil but this is a justified usage.
This creates a versitile telemetry tracking no matter where in the code. Something like a Logger.
No side effect will result in this as it is write-only for code outside of telemetry.
Decorators should be used to minimize logic involving telemetry.
"""
_METRICS: Optional[defaultdict] = None


class MetricName(Enum):
    # Metrics that can be reported only once in a session
    installed = ("installed", True)
    commandRun = ("commandRun", True)

    # Metrics that can be reported any number of times during a session
    # e.g. docker_image_download_status
    templateWarning = ("templateWarning", False)
    runtimeMetric = ("runtimeMetric", False)

    def __init__(self, name: str, can_report_once_only: bool):
        self._name = name
        self.can_report_once_only = can_report_once_only

    def __str__(self) -> str:
        return self._name


def _get_global_metric_sink() -> defaultdict:
    global _METRICS  # pylint: disable=global-statement
    if _METRICS is None:
        _METRICS = defaultdict(list)
    return _METRICS


def flush():
    """
    Emits all metrics to telemetry and flush the metric sink
    """
    telemetry = Telemetry()
    metric_sink = _get_global_metric_sink()
    for metric_list in metric_sink.values():
        while metric_list:
            metric = metric_list.pop(0)
            telemetry.emit(metric)


def track_metric(
    metric_name: MetricName,
    metric_specific_attrs: Optional[Dict[str, Any]] = None,
    overwrite_existing_metric_specific_attrs: bool = False,
    top_level_attrs: Optional[Dict[str, Any]] = None,
    overwrite_existing_top_level_attrs: bool = False,
):
    """
    Generic metric tracker
    Metrics tracked by Generic metric tracker will first be collected into the global metric sink,
    All metrics collected in the global metric sink will be emitted at program exit
    (by calling flush(), see samcli/cli/main.py)

    Examples
    --------
    tracking metric with metric-specific attributes
    >>> track_metric(MetricName.commandRun, {"foo": "bar"})
    >>> track_metric(MetricName.commandRun, metric_specific_attrs={"foo": "bar"})

    overwriting exisitng metric-specific attributes
    (only applicable for metric that can be reported only once, use with caution)
    >>> track_metric(MetricName.commandRun, {"foo": "bar"}, overwrite_existing_metric_specific_attrs=True)

    tracking metric with top-level attributes
    >>> track_metric(MetricName.commandRun, top_level_attrs={"foo": "bar"})

    overwriting exisitng top-level attributes
    (only applicable for metric that can be reported only once, use with caution)
    >>> track_metric(MetricName.commandRun, top_level_attrs={"foo": "bar"}, overwrite_existing_top_level_attrs=True)

    Parameters
    ----------
    metric_name: MetricName
        an instance of MetricName, e.g. MetricName.commandRun
    metric_specific_attrs: dict
        metric specific attributes to track. This is the normally the place where you want to track
        certain attributes for specific metrics.  e.g. tracking usage of 'use-container' for
        sam build command.
    overwrite_existing_metric_specific_attrs: bool
        If certain attribute is already tracked in metric specific attributes, set this flag to True
        to overwrite
    top_level_attrs: dict
        top level attrs to track. These are the attributes that apply to all metrics.
    overwrite_existing_top_level_attrs: bool
        If certain attribute is already tracked in top level attributes, set this flag to True to overwrite
        Note: normally you don't want to overwrite top level attrs
    --
    """
    metric_sink = _get_global_metric_sink()
    if metric_name not in metric_sink or not metric_sink[metric_name] or not metric_name.can_report_once_only:
        metric = Metric(metric_name)
        metric_sink[metric_name].append(metric)
    else:
        metric = metric_sink[metric_name][0]

    metric_specific_attrs = metric_specific_attrs or {}
    for key, val in metric_specific_attrs.items():
        if key not in metric["metricSpecificAttributes"] or overwrite_existing_metric_specific_attrs is True:
            metric["metricSpecificAttributes"][key] = val

    top_level_attrs = top_level_attrs or {}
    for key, val in top_level_attrs.items():
        if key not in metric or overwrite_existing_top_level_attrs is True:
            metric[key] = val


def send_installed_metric():
    LOG.debug("Sending Installed Metric")

    telemetry = Telemetry()
    # NOTE: not using track_metric here because we want to emit the metric right away
    metric = Metric(MetricName.installed)
    metric["osPlatform"] = platform.system()
    metric["telemetryEnabled"] = bool(GlobalConfig().telemetry_enabled)
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
            template_warning_checker = TemplateWarningsChecker()
            ctx = Context.get_current_context()

            try:
                ctx.template_dict
            except AttributeError:
                LOG.debug("Ignoring warning check as template is not provided in context.")
                return func(*args, **kwargs)
            for warning_name in warning_names:
                warning_message = template_warning_checker.check_template_for_warning(warning_name, ctx.template_dict)
                track_metric(
                    MetricName.templateWarning,
                    top_level_attrs={
                        "awsProfileProvided": bool(ctx.profile),
                        "debugFlagProvided": bool(ctx.debug),
                        "region": ctx.region or "",
                        "warningName": warning_name,
                        "warningCount": 1 if warning_message else 0,  # 1-True or 0-False
                    },
                )

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

    def wrapped(*args, **kwargs):
        exception = None
        return_value = None
        exit_reason = "success"
        exit_code = 0

        duration_fn = _timer()
        try:

            # Execute the function and capture return value. This is returned back by the wrapper
            # First argument of all commands should be the Context
            return_value = func(*args, **kwargs)

        except UserException as ex:
            # Capture exception information and re-raise it later so we can first send metrics.
            exception = ex
            exit_code = ex.exit_code
            if ex.wrapped_from is None:
                exit_reason = type(ex).__name__
            else:
                exit_reason = ex.wrapped_from

        except Exception as ex:
            exception = ex
            # Standard Unix practice to return exit code 255 on fatal/unhandled exit.
            exit_code = 255
            exit_reason = type(ex).__name__

        try:
            ctx = Context.get_current_context()
            track_metric(
                MetricName.commandRun,
                top_level_attrs={
                    "awsProfileProvided": bool(ctx.profile),
                    "debugFlagProvided": bool(ctx.debug),
                    "region": ctx.region or "",
                    "commandName": ctx.command_path,
                    "duration": duration_fn(),
                    "exitReason": exit_reason,
                    "exitCode": exit_code,
                },
                # NOTE: setting overwrite_existing_top_level_attrs to True since this is run after the commd logic runs
                # the top_level_attrs tracked here takes precedence
                overwrite_existing_top_level_attrs=True,
            )
        except RuntimeError:
            LOG.debug("Unable to find Click Context for getting session_id.")
        if exception:
            raise exception  # pylint: disable=raising-bad-type

        return return_value

    return wrapped


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


class Metric(MutableMapping):  # pylint: disable=too-many-ancestors
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

    @property
    def name(self):
        return str(self._metric_name)

    @property
    def data(self):
        return self._data

    def _add_common_metric_attributes(self):
        # all metrics (e.g. commandRun, installation) will have these universal attributes
        self._data["requestId"] = str(uuid.uuid4())
        self._data["installationId"] = self._gc.installation_id
        self._data["sessionId"] = self._session_id
        self._data["executionEnvironment"] = self._get_execution_environment()
        self._data["ci"] = bool(self._cicd_detector.platform())
        self._data["pyversion"] = platform.python_version()
        self._data["samcliVersion"] = samcli_version
        # metricSpecificAttributes is for holding attributes that are specific for that metric
        # For example, if we want to track usage of warm containers, the corresponding attribute should go into here
        self._data["metricSpecificAttributes"] = dict()

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

    def __setitem__(self, k: str, v: Any) -> None:
        self._data[k] = v

    def __delitem__(self, v: str) -> None:
        del self._data[v]

    def __getitem__(self, k: str) -> Any:
        return self._data[k]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator:
        return iter(self._data)

    def __bool__(self):
        return bool(self._data)
