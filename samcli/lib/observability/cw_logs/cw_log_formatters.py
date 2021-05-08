"""
Contains all mappers (formatters) for CloudWatch logs
"""
import json

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent
from samcli.lib.observability.observability_info_puller import ObservabilityEventMapper
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.time import timestamp_to_iso


class CWKeywordHighlighterFormatter(ObservabilityEventMapper[CWLogEvent]):
    """
    Mapper implementation which will highlight given keywords in CloudWatch logs
    """

    def __init__(self, colored: Colored, keyword=None):
        """
        Parameters
        ----------
        colored : Colored
            Colored class that will be used to highlight the keywords in log event
        keyword : str
            Keyword that will be highlighted
        """
        self._keyword = keyword
        self._colored = colored

    def map(self, event: CWLogEvent) -> CWLogEvent:
        if self._keyword:
            highlight = self._colored.underline(self._keyword)
            event.message = event.message.replace(self._keyword, highlight)

        return event


class CWColorizeErrorsFormatter(ObservabilityEventMapper[CWLogEvent]):
    """
    Mapper implementation which will colorize some pre-defined error messages
    """

    NODEJS_CRASH_MESSAGE = "Process exited before completing request"
    TIMEOUT_MSG = "Task timed out"

    def __init__(self, colored: Colored):
        self._colored = colored

    def map(self, event: CWLogEvent) -> CWLogEvent:
        if (
            CWColorizeErrorsFormatter.NODEJS_CRASH_MESSAGE in event.message
            or CWColorizeErrorsFormatter.TIMEOUT_MSG in event.message
        ):
            event.message = self._colored.red(event.message)
        return event


class CWJsonFormatter(ObservabilityEventMapper[CWLogEvent]):
    """
    Mapper implementation which will auto indent the input if the input is a JSON object
    """

    # pylint: disable=R0201
    def map(self, event: CWLogEvent) -> CWLogEvent:
        try:
            if event.message.startswith("{"):
                msg_dict = json.loads(event.message)
                event.message = json.dumps(msg_dict, indent=2)
        except Exception:
            pass

        return event


class CWPrettyPrintFormatter(ObservabilityEventMapper[CWLogEvent]):
    """
    Mapper implementation which will format given CloudWatch log event into string with coloring
    log stream name and timestamp
    """

    def __init__(self, colored: Colored):
        self._colored = colored

    # pylint: disable=R0201
    def map(self, event: CWLogEvent) -> str:
        timestamp = self._colored.yellow(timestamp_to_iso(int(event.timestamp)))
        log_stream_name = self._colored.cyan(event.log_stream_name)
        return f"{log_stream_name} {timestamp} {event.message}"
