"""
Contains mapper implementations of XRay events
"""
from copy import deepcopy
from typing import List

from samcli.lib.observability.observability_info_puller import ObservabilityEventMapper
from samcli.lib.observability.xray_traces.xray_events import XRayTraceEvent, XRayTraceSegment


class XRayTraceConsoleMapper(ObservabilityEventMapper[XRayTraceEvent]):
    """
    Maps given XRayTraceEvent.message field into printable format to use it in the console consumer
    """

    def map(self, event: XRayTraceEvent) -> XRayTraceEvent:
        formatted_segments = self.format_segments(event.segments)
        mapped_message = (
            f"\nNew XRay Event with id ({event.id}) and duration ({event.duration:.3f}s)" f"{formatted_segments}"
        )
        event.message = mapped_message

        return event

    def format_segments(self, segments: List[XRayTraceSegment], level: int = 0) -> str:
        """
        Prints given segment information back to console.

        Parameters
        ----------
        segments : List[XRayTraceEvent]
            List of segments which will be printed into console
        level : int
            Optional level value which will be used to make the indentation of each segment. Default value is 0
        """
        formatted_str = ""
        for segment in segments:
            formatted_str += f"\n{'  ' * level} - {segment.get_duration():.3f}s - {segment.name}"
            if segment.http_status:
                formatted_str += f" [HTTP: {segment.http_status}]"
            formatted_str += self.format_segments(segment.sub_segments, (level + 1))

        return formatted_str


class XRayTraceFileMapper(ObservabilityEventMapper[XRayTraceEvent]):
    """
    Original response from xray client contains json in an escaped string. This mapper re-constructs Json object again
    """

    # pylint: disable=R0201
    def map(self, event: XRayTraceEvent) -> XRayTraceEvent:
        mapped_event = deepcopy(event.event)
        segments = [segment.document for segment in event.segments]
        mapped_event["Segments"] = segments
        event.event = mapped_event
        return event
