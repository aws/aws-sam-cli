"""
This file contains puller implementations for XRay
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union

from samcli.lib.observability.observability_info_puller import ObservabilityEventConsumer
from samcli.lib.observability.xray_traces.xray_event_puller import AbstractXRayPuller
from samcli.lib.observability.xray_traces.xray_events import XRayServiceGraphEvent
from samcli.lib.utils.time import to_utc, utc_to_timestamp

LOG = logging.getLogger(__name__)


class XRayServiceGraphPuller(AbstractXRayPuller):
    """
    ObservabilityPuller implementation which pulls XRay Service Graph
    """

    def __init__(
        self, xray_client: Any, consumer: ObservabilityEventConsumer, max_retries: int = 1000, poll_interval: int = 1
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
        super().__init__(max_retries, poll_interval)
        self.xray_client = xray_client
        self.consumer = consumer
        self._previous_xray_service_graphs: Set[str] = set()

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
                    utc_end_time = to_utc(event_end_time)
                    latest_event_time = utc_to_timestamp(utc_end_time)
                    if latest_event_time > self.latest_event_time:
                        self.latest_event_time = latest_event_time + 1

                self._had_data = True
                xray_service_graph_event = XRayServiceGraphEvent(result)
                if xray_service_graph_event.get_hash() not in self._previous_xray_service_graphs:
                    self.consumer.consume(xray_service_graph_event)
                self._previous_xray_service_graphs.add(xray_service_graph_event.get_hash())

    def load_events(self, event_ids: Union[List[Any], Dict]):
        LOG.debug("Loading specific service graph events are not supported via XRay Service Graph")
