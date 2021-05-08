"""
CloudWatch log event puller implementation
"""
import logging
import time
from datetime import datetime
from typing import Optional, Any

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent
from samcli.lib.observability.observability_info_puller import ObservabilityPuller, ObservabilityEventConsumer
from samcli.lib.utils.time import to_timestamp, to_datetime

LOG = logging.getLogger(__name__)


class CWLogPuller(ObservabilityPuller):
    """
    Puller implementation that can pull events from CloudWatch log group
    """

    def __init__(
        self,
        logs_client: Any,
        consumer: ObservabilityEventConsumer,
        cw_log_group: str,
        resource_name: Optional[str] = None,
        max_retries: int = 1000,
        poll_interval: int = 1,
    ):
        """
        Parameters
        ----------
        logs_client: Any
            boto3 logs client instance
        consumer : ObservabilityEventConsumer
            Consumer instance that will process pulled events
        cw_log_group : str
            CloudWatch log group name
        resource_name : Optional[str]
            Optional parameter to assign a resource name for each event.
        max_retries: int
            Optional parameter to set maximum retries when tailing. Default value is 1000
        poll_interval: int
            Optional parameter to define sleep interval between pulling new log events when tailing. Default value is 1
        """
        self.logs_client = logs_client
        self.consumer = consumer
        self.cw_log_group = cw_log_group
        self.resource_name = resource_name
        self._max_retries = max_retries
        self._poll_interval = poll_interval
        self.latest_event_time = 0
        self.had_data = False

    def tail(self, start_time: Optional[datetime] = None, filter_pattern: Optional[str] = None):
        if start_time:
            self.latest_event_time = to_timestamp(start_time)

        counter = self._max_retries
        while counter > 0:
            LOG.debug("Tailing logs from %s starting at %s", self.cw_log_group, str(self.latest_event_time))

            counter -= 1
            self.load_time_period(to_datetime(self.latest_event_time), filter_pattern=filter_pattern)

            # This poll fetched logs. Reset the retry counter and set the timestamp for next poll
            if self.had_data:
                counter = self._max_retries
                self.latest_event_time += 1  # one extra millisecond to fetch next log event
                self.had_data = False

            # We already fetched logs once. Sleep for some time before querying again.
            # This also helps us scoot under the TPS limit for CloudWatch API call.
            time.sleep(self._poll_interval)

    def load_time_period(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filter_pattern: Optional[str] = None,
    ):
        kwargs = {"logGroupName": self.cw_log_group, "interleaved": True}

        if start_time:
            kwargs["startTime"] = to_timestamp(start_time)

        if end_time:
            kwargs["endTime"] = to_timestamp(end_time)

        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern

        while True:
            LOG.debug("Fetching logs from CloudWatch with parameters %s", kwargs)
            result = self.logs_client.filter_log_events(**kwargs)

            # Several events will be returned. Yield one at a time
            for event in result.get("events", []):
                self.had_data = True
                cw_event = CWLogEvent(self.cw_log_group, event, self.resource_name)

                if cw_event.timestamp > self.latest_event_time:
                    self.latest_event_time = cw_event.timestamp

                self.consumer.consume(cw_event)

            # Keep iterating until there are no more logs left to query.
            next_token = result.get("nextToken", None)
            kwargs["nextToken"] = next_token
            if not next_token:
                break
