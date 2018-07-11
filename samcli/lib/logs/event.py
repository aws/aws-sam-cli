"""
Represents CloudWatch Log Event
"""

import logging

from samcli.lib.utils.time import timestamp_to_iso

LOG = logging.getLogger(__name__)


class LogEvent(object):
    """
    Data object representing a CloudWatch Log Event
    """

    log_group_name = None
    log_stream_name = None
    timestamp = None
    message = None

    def __init__(self, log_group_name, event_dict):
        """
        Creates instance of the class

        Parameters
        ----------
        event_dict : dict
            Dict of log event data returned by CloudWatch Logs API.
            https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_FilteredLogEvent.html
        """

        self.log_group_name = log_group_name

        if not event_dict:
            # If event is empty, just use default values for properties. We don't raise an error here because
            # this class is a data wrapper to the `events_dict`. It doesn't try to be smart.
            return

        self.log_stream_name = event_dict.get('logStreamName')
        self.message = event_dict.get('message', '')

        self.timestamp_millis = event_dict.get('timestamp')

        # Convert the timestamp from epoch to readable ISO timestamp, easier for formatting.
        if self.timestamp_millis:
            self.timestamp = timestamp_to_iso(int(self.timestamp_millis))

    def __eq__(self, other):

        if not isinstance(other, LogEvent):
            return False

        return self.log_group_name == other.log_group_name \
            and self.log_stream_name == other.log_stream_name \
            and self.timestamp == other.timestamp \
            and self.message == other.message

    def __repr__(self):  # pragma: no cover
        # Used to print pretty diff when testing
        return str({
            "log_group_name": self.log_group_name,
            "log_stream_name": self.log_stream_name,
            "message": self.message,
            "timestamp": self.timestamp
        })
