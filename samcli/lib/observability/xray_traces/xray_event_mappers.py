"""
Contains mapper implementations of XRay events
"""
import json
from copy import deepcopy
from datetime import datetime
from typing import List

from samcli.lib.observability.observability_info_puller import ObservabilityEventMapper
from samcli.lib.observability.xray_traces.xray_events import (
    XRayTraceEvent,
    XRayTraceSegment,
    XRayServiceGraphEvent,
    XRayGraphServiceInfo,
)
from samcli.lib.utils.time import to_utc, utc_to_timestamp, timestamp_to_iso


class XRayTraceConsoleMapper(ObservabilityEventMapper[XRayTraceEvent]):
    """
    Maps given XRayTraceEvent.message field into printable format to use it in the console consumer
    """

    def map(self, event: XRayTraceEvent) -> XRayTraceEvent:
        formatted_segments = self.format_segments(event.segments)
        iso_formatted_timestamp = datetime.fromtimestamp(event.timestamp).isoformat()
        revision_info = f"[revision {event.revision}] " if event.revision else ""
        mapped_message = (
            f"\nXRay Event {revision_info}at ({iso_formatted_timestamp}) with \
id ({event.id}) and duration ({event.duration:.3f}s)"
            f"{formatted_segments}"
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


class XRayTraceJSONMapper(ObservabilityEventMapper[XRayTraceEvent]):
    """
    Original response from xray client contains json in an escaped string. This mapper re-constructs Json object again
    and converts into JSON string that can be printed into console.
    """

    # pylint: disable=R0201
    def map(self, event: XRayTraceEvent) -> XRayTraceEvent:
        mapped_event = deepcopy(event.event)
        segments = [segment.document for segment in event.segments]
        mapped_event["Segments"] = segments
        event.event = mapped_event
        event.message = json.dumps(mapped_event)
        return event


class XRayServiceGraphConsoleMapper(ObservabilityEventMapper[XRayServiceGraphEvent]):
    """
    Maps given XRayServiceGraphEvent.message field into printable format to use it in the console consumer
    """

    def map(self, event: XRayServiceGraphEvent) -> XRayServiceGraphEvent:
        formatted_services = self.format_services(event.services)
        mapped_message = "\nNew XRay Service Graph"
        mapped_message += f"\n  Start time: {event.start_time}"
        mapped_message += f"\n  End time: {event.end_time}"
        mapped_message += formatted_services
        event.message = mapped_message

        return event

    def format_services(self, services: List[XRayGraphServiceInfo]) -> str:
        """
        Prints given services information back to console.

        Parameters
        ----------
        services : List[XRayGraphServiceInfo]
            List of services which will be printed into console
        """
        formatted_str = ""
        for service in services:
            formatted_str += f"\n  Reference Id: {service.id}"
            formatted_str += f"{ ' - (Root)' if service.is_root else ' -'}"
            formatted_str += f" {service.type} - {service.name}"
            formatted_str += f" - Edges: {self.format_edges(service)}"
            formatted_str += self.format_summary_statistics(service, 1)

        return formatted_str

    @staticmethod
    def format_edges(service: XRayGraphServiceInfo) -> str:
        edge_ids = service.edge_ids
        return str(edge_ids)

    @staticmethod
    def format_summary_statistics(service: XRayGraphServiceInfo, level) -> str:
        """
        Prints given summary statistics information back to console.

        Parameters
        ----------
        service: XRayGraphServiceInfo
            summary statistics of the service which will be printed into console
        level : int
            Optional level value which will be used to make the indentation of each segment. Default value is 0
        """
        formatted_str = f"\n{'  ' * level} Summary_statistics:"
        formatted_str += f"\n{'  ' * (level + 1)} - total requests: {service.total_count}"
        formatted_str += f"\n{'  ' * (level + 1)} - ok count(2XX): {service.ok_count}"
        formatted_str += f"\n{'  ' * (level + 1)} - error count(4XX): {service.error_count}"
        formatted_str += f"\n{'  ' * (level + 1)} - fault count(5XX): {service.fault_count}"
        formatted_str += f"\n{'  ' * (level + 1)} - total response time: {service.response_time}"
        return formatted_str


class XRayServiceGraphJSONMapper(ObservabilityEventMapper[XRayServiceGraphEvent]):
    """
    Original response from xray client contains datetime object. This mapper convert datetime object to iso string,
    and converts final JSON object into string.
    """

    def map(self, event: XRayServiceGraphEvent) -> XRayServiceGraphEvent:
        mapped_event = deepcopy(event.event)

        self._convert_start_and_end_time_to_iso(mapped_event)
        services = mapped_event.get("Services", [])
        for service in services:
            self._convert_start_and_end_time_to_iso(service)
            edges = service.get("Edges", [])
            for edge in edges:
                self._convert_start_and_end_time_to_iso(edge)

        event.event = mapped_event
        event.message = json.dumps(mapped_event)
        return event

    def _convert_start_and_end_time_to_iso(self, event):
        self.convert_event_datetime_to_iso(event, "StartTime")
        self.convert_event_datetime_to_iso(event, "EndTime")

    def convert_event_datetime_to_iso(self, event, datetime_key):
        event_datetime = event.get(datetime_key, None)
        if event_datetime:
            event[datetime_key] = self.convert_local_datetime_to_iso(event_datetime)

    @staticmethod
    def convert_local_datetime_to_iso(local_datetime):
        utc_datetime = to_utc(local_datetime)
        time_stamp = utc_to_timestamp(utc_datetime)
        return timestamp_to_iso(time_stamp)
