"""
Provides methods to generate and send metrics
"""


import platform
import logging

from timeit import default_timer

from samcli.cli.context import Context
from samcli.commands.exceptions import UserException
from samcli.cli.global_config import GlobalConfig
from .telemetry import Telemetry


LOG = logging.getLogger(__name__)


def send_installed_metric():

    LOG.debug("Sending Installed Metric")

    telemetry = Telemetry()
    telemetry.emit("installed", {"osPlatform": platform.system(), "telemetryEnabled": _telemetry_enabled()})


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

        if not _telemetry_enabled():
            # When Telemetry is disabled, call the function immediately and return.
            return func(*args, **kwargs)

        telemetry = Telemetry()

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

        ctx = Context.get_current_context()
        telemetry.emit(
            "commandRun",
            {
                # Metric about command's general environment
                "awsProfileProvided": bool(ctx.profile),
                "debugFlagProvided": bool(ctx.debug),
                "region": ctx.region or "",
                "commandName": ctx.command_path,  # Full command path. ex: sam local start-api
                # Metric about command's execution characteristics
                "duration": duration_fn(),
                "exitReason": exit_reason,
                "exitCode": exit_code,
            },
        )

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


def _telemetry_enabled():
    gc = GlobalConfig()
    return bool(gc.telemetry_enabled)
