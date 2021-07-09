"""
This file contains puller implementations for XRay
"""
import logging
import time
from datetime import datetime
from typing import Optional, Any, List, Set

from botocore.exceptions import ClientError

from samcli.lib.observability.observability_info_puller import ObservabilityPuller, ObservabilityEventConsumer
from samcli.lib.observability.xray_traces.xray_events import XRayServiceGraphEvent
from samcli.lib.utils.time import to_timestamp, to_datetime, to_utc, utc_to_timestamp

LOG = logging.getLogger(__name__)


class XRayServiceGraphPuller(ObservabilityPuller):
    """
    ObservabilityPuller implementation which pulls XRay Service Graph
    """

    def __init__(
        self,
        xray_client: Any,
        consumer: ObservabilityEventConsumer,
        max_retries: int = 1000,
        poll_interval: int = 1,
    ):
        """
        Parameters
        ----------
        xray_client : boto3.client
            XRay boto3 client instance
        consumer :  ObservabilityEventConsumer
            Consumer instance which will process pulled events
        max_retries : int
            Optional maximum number of retries which can be used to pull information. Default value is 1000
        poll_interval : int
            Optional interval value that will be used to wait between calls in tail operation. Default value is 1
        """
        self.xray_client = xray_client
        self.consumer = consumer
        self.latest_event_time = 0
        self._max_retries = max_retries
        self._poll_interval = poll_interval
        self._had_data = False
        self._previous_trace_ids: Set[str] = set()

    def tail(self, start_time: Optional[datetime] = None, filter_pattern: Optional[str] = None):
        if start_time:
            self.latest_event_time = to_timestamp(start_time)

        counter = self._max_retries
        while counter > 0:
            LOG.debug("Tailing XRay traces starting at %s", self.latest_event_time)

            counter -= 1
            try:
                self.load_time_period(to_datetime(self.latest_event_time), datetime.utcnow())
            except ClientError as err:
                error_code = err.response.get("Error", {}).get("Code")
                if error_code == "ThrottlingException":
                    # if throttled, increase poll interval by 1 second each time
                    if self._poll_interval == 1:
                        self._poll_interval += 1
                    else:
                        self._poll_interval **= 2
                    LOG.warning(
                        "Throttled by XRay API, increasing the poll interval time to %s seconds",
                        self._poll_interval,
                    )
                else:
                    # if exception is other than throttling re-raise
                    LOG.error("Failed while fetching new AWS X-Ray Service Graph events", exc_info=err)
                    raise err

            if self._had_data:
                counter = self._max_retries
                self.latest_event_time += 1
                self._had_data = False

            time.sleep(self._poll_interval)

    def load_time_period(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filter_pattern: Optional[str] = None,
    ):
        # pull xray traces service graph
        kwargs = {"StartTime": start_time, "EndTime": end_time}
        result_paginator = self.xray_client.get_paginator("get_service_graph")
        result_iterator = result_paginator.paginate(**kwargs)
        for result in result_iterator:
            services = result.get("Services", [])

            if not services:
                LOG.debug("No service graph found%s")
            else:
                # update latest fetched event
                event_end_time = result.get("EndTime", None)
                if event_end_time:
                    # end_time is in local time zone, need to convert to utc first
                    utc_end_time = to_utc(event_end_time)
                    latest_event_time = utc_to_timestamp(utc_end_time)
                    if latest_event_time > self.latest_event_time:
                        self.latest_event_time = latest_event_time + 1
                self._had_data = True
                xray_service_graph_event = XRayServiceGraphEvent(result)
                self.consumer.consume(xray_service_graph_event)

    def load_events(self, event_ids: List[str]):
        LOG.debug("Loading specific service graph events are not supported via XRay Service Graph")
