"""
Contains all mappers (formatters) for CloudWatch logs
"""

import json
import logging
from json import JSONDecodeError
from typing import Any

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent
from samcli.lib.observability.observability_info_puller import ObservabilityEventMapper
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.time import timestamp_to_iso

LOG = logging.getLogger(__name__)


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

    # couple of pre-defined error messages for lambda functions which will be colorized when getting the logs
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
    # Pylint recommends converting this method to a static one but we want it to stay as it is
    # since formatters/mappers are combined in an array of ObservabilityEventMapper class
    def map(self, event: CWLogEvent) -> CWLogEvent:
        try:
            if event.message.startswith("{"):
                msg_dict = json.loads(event.message)
                event.message = json.dumps(msg_dict, indent=2)
        except JSONDecodeError as err:
            LOG.debug("Can't decode string (%s) as JSON. Error (%s)", event.message, err)

        return event


class CWPrettyPrintFormatter(ObservabilityEventMapper[CWLogEvent]):
    """
    Mapper implementation which will format given CloudWatch log event into string with coloring
    log stream name and timestamp
    """

    def __init__(self, colored: Colored):
        self._colored = colored

    def map(self, event: CWLogEvent) -> CWLogEvent:
        timestamp = self._colored.yellow(timestamp_to_iso(int(event.timestamp)))
        log_stream_name = self._colored.cyan(event.log_stream_name)
        event.message = f"{log_stream_name} {timestamp} {event.message}"
        return event


class CWAddNewLineIfItDoesntExist(ObservabilityEventMapper):
    """
    Mapper implementation which will add new lines at the end of events if it is not already there
    """

    def map(self, event: Any) -> Any:
        # if it is a CWLogEvent, append new line at the end of event.message
        if isinstance(event, CWLogEvent) and not event.message.endswith("\n"):
            event.message = f"{event.message}\n"
            return event
        # if event is a string, then append new line at the end of the string
        if isinstance(event, str) and not event.endswith("\n"):
            return f"{event}\n"
        # no-action for unknown events
        return event


class CWLogEventJSONMapper(ObservabilityEventMapper[CWLogEvent]):
    """
    Converts given CWLogEvent into JSON string
    """

    # pylint: disable=no-self-use
    def map(self, event: CWLogEvent) -> CWLogEvent:
        event.message = json.dumps(event.event)
        return event
