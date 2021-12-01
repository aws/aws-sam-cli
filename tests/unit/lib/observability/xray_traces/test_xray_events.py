import json
import time
import uuid
from unittest import TestCase

from samcli.lib.observability.xray_traces.xray_events import XRayTraceSegment, XRayTraceEvent, XRayServiceGraphEvent
from samcli.lib.utils.hash import str_checksum

LATEST_EVENT_TIME = 9621490723


class AbstractXRayEventTextTest(TestCase):
    def validate_segment(self, segment, event_dict):
        self.assertEqual(segment.id, event_dict.get("Id"))
        self.assertEqual(segment.name, event_dict.get("name"))
        self.assertEqual(segment.start_time, event_dict.get("start_time"))
        self.assertEqual(segment.end_time, event_dict.get("end_time"))
        self.assertEqual(segment.http_status, event_dict.get("http", {}).get("response", {}).get("status", None))
        event_subsegments = event_dict.get("subsegments", [])
        self.assertEqual(len(segment.sub_segments), len(event_subsegments))

        for event_subsegment in event_subsegments:
            subsegment = next(x for x in segment.sub_segments if x.id == event_subsegment.get("Id"))
            self.validate_segment(subsegment, event_subsegment)


class TestXRayTraceEvent(AbstractXRayEventTextTest):
    def setUp(self):
        self.first_segment_date = time.time() - 1000
        self.segment_1 = {
            "Id": str(uuid.uuid4()),
            "name": f"Second {str(uuid.uuid4())}",
            "start_time": time.time(),
            "end_time": time.time(),
            "http": {"response": {"status": 200}},
        }
        self.segment_2 = {
            "Id": str(uuid.uuid4()),
            "name": f"First {str(uuid.uuid4())}",
            "start_time": self.first_segment_date,
            "end_time": LATEST_EVENT_TIME,
            "http": {"response": {"status": 200}},
        }
        self.event_dict = {
            "Id": str(uuid.uuid4()),
            "Duration": 400,
            "Segments": [
                {"Id": self.segment_1.get("Id"), "Document": json.dumps(self.segment_1)},
                {"Id": self.segment_2.get("Id"), "Document": json.dumps(self.segment_2)},
            ],
        }

    def test_xray_trace_event(self):
        xray_trace_event = XRayTraceEvent(self.event_dict)
        self.assertEqual(xray_trace_event.id, self.event_dict.get("Id"))
        self.assertEqual(xray_trace_event.duration, self.event_dict.get("Duration"))
        segments = self.event_dict.get("Segments", [])
        self.assertEqual(len(xray_trace_event.segments), len(segments))

        for segment in segments:
            subsegment = next(x for x in xray_trace_event.segments if x.id == segment.get("Id"))
            self.validate_segment(subsegment, json.loads(segment.get("Document")))

    def test_latest_event_time(self):
        xray_trace_event = XRayTraceEvent(self.event_dict)
        self.assertEqual(xray_trace_event.get_latest_event_time(), LATEST_EVENT_TIME)

    def test_first_event_time(self):
        xray_trace_event = XRayTraceEvent(self.event_dict)
        self.assertEqual(xray_trace_event.timestamp, self.first_segment_date)

    def test_segment_order(self):
        xray_trace_event = XRayTraceEvent(self.event_dict)

        self.assertEqual(len(xray_trace_event.segments), 2)
        self.assertIn("First", xray_trace_event.segments[0].name)
        self.assertIn("Second", xray_trace_event.segments[1].name)


class TestXRayTraceSegment(AbstractXRayEventTextTest):
    def setUp(self):
        self.event_dict = {
            "Id": uuid.uuid4(),
            "name": uuid.uuid4(),
            "start_time": time.time(),
            "end_time": time.time(),
            "http": {"response": {"status": 200}},
            "subsegments": [
                {
                    "Id": uuid.uuid4(),
                    "name": uuid.uuid4(),
                    "start_time": time.time(),
                    "end_time": time.time(),
                    "http": {"response": {"status": 200}},
                },
                {
                    "Id": uuid.uuid4(),
                    "name": uuid.uuid4(),
                    "start_time": time.time(),
                    "end_time": time.time(),
                    "http": {"response": {"status": 200}},
                    "subsegments": [
                        {
                            "Id": uuid.uuid4(),
                            "name": uuid.uuid4(),
                            "start_time": time.time(),
                            "end_time": LATEST_EVENT_TIME,
                            "http": {"response": {"status": 200}},
                        }
                    ],
                },
            ],
        }

    def test_xray_trace_segment_duration(self):
        xray_trace_segment = XRayTraceSegment(self.event_dict)
        self.assertEqual(
            xray_trace_segment.get_duration(), self.event_dict.get("end_time") - self.event_dict.get("start_time")
        )

    def test_xray_latest_event_time(self):
        xray_trace_segment = XRayTraceSegment(self.event_dict)
        self.assertEqual(xray_trace_segment.get_latest_event_time(), LATEST_EVENT_TIME)

    def test_xray_trace_segment(self):
        xray_trace_segment = XRayTraceSegment(self.event_dict)
        self.validate_segment(xray_trace_segment, self.event_dict)


class AbstractXRayServiceTest(TestCase):
    def validate_service(self, service, service_dict):
        self.assertEqual(service.id, service_dict.get("ReferenceId"))
        self.assertEqual(service.name, service_dict.get("Name"))
        self.assertEqual(service.is_root, service_dict.get("Root"))
        self.assertEqual(service.type, service_dict.get("Type"))
        self.assertEqual(service.name, service_dict.get("Name"))
        edges = service_dict.get("Edges")
        self.assertEqual(len(service.edge_ids), len(edges))
        summary_statistics = service_dict.get("SummaryStatistics")
        self.assertEqual(service.ok_count, summary_statistics.get("OkCount"))
        self.assertEqual(service.error_count, summary_statistics.get("ErrorStatistics").get("TotalCount"))
        self.assertEqual(service.fault_count, summary_statistics.get("FaultStatistics").get("TotalCount"))
        self.assertEqual(service.total_count, summary_statistics.get("TotalCount"))
        self.assertEqual(service.response_time, summary_statistics.get("TotalResponseTime"))


class TestXRayServiceGraphEvent(AbstractXRayServiceTest):
    def setUp(self):
        self.service_1 = {
            "ReferenceId": 0,
            "Name": "test1",
            "Root": True,
            "Type": "Lambda",
            "Edges": [
                {
                    "ReferenceId": 1,
                },
            ],
            "SummaryStatistics": {
                "OkCount": 1,
                "ErrorStatistics": {"TotalCount": 2},
                "FaultStatistics": {"TotalCount": 3},
                "TotalCount": 6,
                "TotalResponseTime": 123.0,
            },
        }

        self.service_2 = {
            "ReferenceId": 1,
            "Name": "test2",
            "Root": False,
            "Type": "Api",
            "Edges": [],
            "SummaryStatistics": {
                "OkCount": 2,
                "ErrorStatistics": {"TotalCount": 3},
                "FaultStatistics": {"TotalCount": 3},
                "TotalCount": 8,
                "TotalResponseTime": 200.0,
            },
        }
        self.event_dict = {
            "Services": [self.service_1, self.service_2],
        }

    def test_xray_service_graph_event(self):
        xray_service_graph_event = XRayServiceGraphEvent(self.event_dict)
        services_array = self.event_dict.get("Services", [])
        services = xray_service_graph_event.services
        self.assertEqual(len(services), len(services_array))

        for service, service_dict in zip(services, services_array):
            self.validate_service(service, service_dict)

    def test__xray_service_graph_event_get_hash(self):
        xray_service_graph_event = XRayServiceGraphEvent(self.event_dict)
        expected_hash = str_checksum(str(self.event_dict["Services"]))
        self.assertEqual(expected_hash, xray_service_graph_event.get_hash())
