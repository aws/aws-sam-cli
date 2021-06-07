import json
import time
import uuid
from unittest import TestCase

from samcli.lib.observability.xray_traces.xray_events import XRayTraceSegment, XRayTraceEvent

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
        self.segment_1 = {
            "Id": str(uuid.uuid4()),
            "name": str(uuid.uuid4()),
            "start_time": time.time(),
            "end_time": time.time(),
            "http": {"response": {"status": 200}},
        }
        self.segment_2 = {
            "Id": str(uuid.uuid4()),
            "name": str(uuid.uuid4()),
            "start_time": time.time(),
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
