
import datetime
import logging

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

        LOG.debug(event_dict)

        self.log_group_name = log_group_name
        self.log_stream_name = event_dict.get('logStreamName')
        self.message = event_dict.get('message', '').strip()

        self.timestamp = event_dict.get('timestamp')

        # Convert the timestamp from epoch to readable ISO timestamp, easier for formatting.
        if self.timestamp:
            timestamp_secs = int(self.timestamp) / 1000
            self._timestamp_datetime = datetime.datetime.utcfromtimestamp(timestamp_secs)
            self.timestamp = self._timestamp_datetime.isoformat()
