"""
Keeps XRay event definitions
"""
import json
import operator
from typing import List, Optional

from samcli.lib.observability.observability_info_puller import ObservabilityEvent
from samcli.lib.utils.hash import str_checksum

start_time_getter = operator.attrgetter("start_time")


class XRayTraceEvent(ObservabilityEvent[dict]):
    """
    Represents a result of each XRay trace event, which is returned by boto3 client by calling 'batch_get_traces'
    See XRayTracePuller
    """

    def __init__(self, event: dict, revision: Optional[int] = None):
        super().__init__(event, 0)
        self.id = event.get("Id", "")
        # A revision number will be passed to link with the event
        # The same x-ray event will differ in information on different revisions
        self.revision = revision
        self.duration = event.get("Duration", 0.0)
        self.message = json.dumps(event)
        self.segments: List[XRayTraceSegment] = []

        self._construct_segments(event)
        if self.segments:
            self.timestamp = self.segments[0].start_time

    def _construct_segments(self, event_dict):
        """
        Each event is represented by segment, and it is like a Tree model (each segment also have subsegments).
        """
        raw_segments = event_dict.get("Segments", [])
        for raw_segment in raw_segments:
            segment_document = raw_segment.get("Document", "{}")
            self.segments.append(XRayTraceSegment(json.loads(segment_document)))
        self.segments.sort(key=start_time_getter)

    def get_latest_event_time(self):
        """
        Returns the latest event time for this specific XRayTraceEvent by calling get_latest_event_time for each segment
        """
        latest_event_time = 0
        for segment in self.segments:
            segment_latest_event_time = segment.get_latest_event_time()
            if segment_latest_event_time > latest_event_time:
                latest_event_time = segment_latest_event_time

        return latest_event_time


class XRayTraceSegment:
    """
    Represents each segment information for a XRayTraceEvent
    """

    def __init__(self, document: dict):
        self.id = document.get("Id", "")
        self.document = document
        self.name = document.get("name", "")
        self.start_time = document.get("start_time", 0)
        self.end_time = document.get("end_time", 0)
        self.http_status = document.get("http", {}).get("response", {}).get("status", None)
        self.sub_segments: List[XRayTraceSegment] = []

        sub_segments = document.get("subsegments", [])
        for sub_segment in sub_segments:
            self.sub_segments.append(XRayTraceSegment(sub_segment))
        self.sub_segments.sort(key=start_time_getter)

    def get_duration(self):
        return self.end_time - self.start_time

    def get_latest_event_time(self):
        """
        Gets the latest event time by comparing all timestamps (end_time) from current segment and all sub-segments
        """
        latest_event_time = self.end_time
        for sub_segment in self.sub_segments:
            sub_segment_latest_time = sub_segment.get_latest_event_time()
            if sub_segment_latest_time > latest_event_time:
                latest_event_time = sub_segment_latest_time

        return latest_event_time


class XRayServiceGraphEvent(ObservabilityEvent[dict]):
    """
    Represents a result of each XRay service graph event, which is returned by boto3 client by calling
    'get_service_graph' See XRayServiceGraphPuller
    """

    def __init__(self, event: dict):
        self.services: List[XRayGraphServiceInfo] = []
        self.message = str(event)
        self._construct_service(event)
        self.start_time = event.get("StartTime", None)
        self.end_time = event.get("EndTime", None)
        super().__init__(event, 0)

    def _construct_service(self, event_dict):
        services = event_dict.get("Services", [])
        for service in services:
            self.services.append(XRayGraphServiceInfo(service))

    def get_hash(self):
        """
        get the hash of the containing services
        """
        services = self.event.get("Services", [])
        return str_checksum(str(services))


class XRayGraphServiceInfo:
    """
    Represents each services information for a XRayServiceGraphEvent
    """

    def __init__(self, service: dict):
        self.id = service.get("ReferenceId", "")
        self.document = service
        self.name = service.get("Name", "")
        self.is_root = service.get("Root", False)
        self.type = service.get("Type")
        self.edge_ids: List[int] = []
        self.ok_count = 0
        self.error_count = 0
        self.fault_count = 0
        self.total_count = 0
        self.response_time = 0
        self._construct_edge_ids(service.get("Edges", []))
        self._set_summary_statistics(service.get("SummaryStatistics", None))

    def _construct_edge_ids(self, edges):
        """
        covert the edges information to a list of edge reference ids
        """
        edge_ids: List[int] = []
        for edge in edges:
            edge_ids.append(edge.get("ReferenceId", -1))
        self.edge_ids = edge_ids

    def _set_summary_statistics(self, summary_statistics):
        """
        get some useful information from summary statistics
        """
        if not summary_statistics:
            return
        self.ok_count = summary_statistics.get("OkCount", 0)
        error_statistics = summary_statistics.get("ErrorStatistics", None)
        if error_statistics:
            self.error_count = error_statistics.get("TotalCount", 0)
        fault_statistics = summary_statistics.get("FaultStatistics", None)
        if fault_statistics:
            self.fault_count = fault_statistics.get("TotalCount", 0)
        self.total_count = summary_statistics.get("TotalCount", 0)
        self.response_time = summary_statistics.get("TotalResponseTime", 0)
