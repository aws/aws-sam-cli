"""
Keeps XRay event definitions
"""
import json
from typing import List

from samcli.lib.observability.observability_info_puller import ObservabilityEvent


class XRayTraceEvent(ObservabilityEvent[dict]):
    """
    Represents a result of each XRay trace event, which is returned by boto3 client by calling 'batch_get_traces'
    See XRayTracePuller
    """

    def __init__(self, event: dict):
        self.id = event.get("Id", "")
        self.duration = event.get("Duration", 0.0)
        self.message = json.dumps(event)

        self.segments: List[XRayTraceSegment] = []
        self._construct_segments(event)

        super().__init__(event, 0)

    def _construct_segments(self, event_dict):
        """
        Each event is represented by segment, and it is like a Tree model (each segment also have subsegments).
        """
        raw_segments = event_dict.get("Segments", [])
        for raw_segment in raw_segments:
            segment_document = raw_segment.get("Document", "{}")
            self.segments.append(XRayTraceSegment(json.loads(segment_document)))

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
