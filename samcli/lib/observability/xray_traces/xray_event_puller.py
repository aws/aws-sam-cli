"""
This file contains puller implementations for XRay
"""
import logging
import time
from datetime import datetime
from itertools import zip_longest
from typing import Optional, Any, List, Set, Dict

from botocore.exceptions import ClientError

from samcli.lib.observability.observability_info_puller import ObservabilityPuller, ObservabilityEventConsumer
from samcli.lib.observability.xray_traces.xray_events import XRayTraceEvent
from samcli.lib.utils.time import to_timestamp, to_datetime

LOG = logging.getLogger(__name__)


class AbstractXRayPuller(ObservabilityPuller):
    def __init__(
        self,
        max_retries: int = 1000,
        poll_interval: int = 1,
    ):
        """
        Parameters
        ----------
        max_retries : int
            Optional maximum number of retries which can be used to pull information. Default value is 1000
        poll_interval : int
            Optional interval value that will be used to wait between calls in tail operation. Default value is 1
        """
        self._max_retries = max_retries
        self._poll_interval = poll_interval
        self._had_data = False
        self.latest_event_time = 0

    def tail(self, start_time: Optional[datetime] = None, filter_pattern: Optional[str] = None):
        if start_time:
            self.latest_event_time = to_timestamp(start_time)

        counter = self._max_retries
        while counter > 0 and not self.cancelled:
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
                    LOG.error("Failed while fetching new AWS X-Ray events", exc_info=err)
                    raise err

            if self._had_data:
                counter = self._max_retries
                self.latest_event_time += 1
                self._had_data = False

            time.sleep(self._poll_interval)


class XRayTracePuller(AbstractXRayPuller):
    """
    ObservabilityPuller implementation which pulls XRay trace information by summarizing XRay traces first
    and then getting them as a batch later.
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
        self._previous_trace_ids: Set[str] = set()

    def load_time_period(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filter_pattern: Optional[str] = None,
    ):
        kwargs = {"TimeRangeType": "TraceId", "StartTime": start_time, "EndTime": end_time}

        # first, collect all trace ids in given period
        trace_ids = []
        LOG.debug("Fetching XRay trace summaries %s", kwargs)
        result_paginator = self.xray_client.get_paginator("get_trace_summaries")
        result_iterator = result_paginator.paginate(**kwargs)
        for result in result_iterator:
            trace_summaries = result.get("TraceSummaries", [])
            for trace_summary in trace_summaries:
                trace_id = trace_summary.get("Id", None)
                is_partial = trace_summary.get("IsPartial", False)
                if not is_partial and trace_id not in self._previous_trace_ids:
                    trace_ids.append(trace_id)
                    self._previous_trace_ids.add(trace_id)

        # now load collected events
        self.load_events(trace_ids)

    def load_events(self, event_ids: List[str]):
        if not event_ids:
            LOG.debug("Nothing to fetch, empty event_id list given (%s)", event_ids)
            return

        # xray client only accepts 5 items at max, so create batches of 5 element arrays
        event_batches = zip_longest(*([iter(event_ids)] * 5))

        for event_batch in event_batches:
            kwargs: Dict[str, Any] = {"TraceIds": list(filter(None, event_batch))}
            result_paginator = self.xray_client.get_paginator("batch_get_traces")
            result_iterator = result_paginator.paginate(**kwargs)
            for result in result_iterator:
                traces = result.get("Traces", [])

                if not traces:
                    LOG.debug("No event found with given trace ids %s", str(event_ids))

                for trace in traces:
                    self._had_data = True
                    xray_trace_event = XRayTraceEvent(trace)

                    # update latest fetched event
                    latest_event_time = xray_trace_event.get_latest_event_time()
                    if latest_event_time > self.latest_event_time:
                        self.latest_event_time = latest_event_time

                    self.consumer.consume(xray_trace_event)
