import json
import time
import uuid
from unittest import TestCase

from samcli.lib.observability.xray_traces.xray_event_mappers import XRayTraceConsoleMapper, XRayTraceFileMapper
from samcli.lib.observability.xray_traces.xray_events import XRayTraceEvent


class AbstraceXRayTraceMapperTest(TestCase):
    def setUp(self):
        self.trace_event = XRayTraceEvent(
            {
                "Id": str(uuid.uuid4()),
                "name": str(uuid.uuid4()),
                "start_time": time.time(),
                "end_time": time.time(),
                "http": {"response": {"status": 200}},
                "subsegments": [
                    {
                        "Id": str(uuid.uuid4()),
                        "Document": json.dumps(
                            {
                                "name": str(uuid.uuid4()),
                                "start_time": time.time(),
                                "end_time": time.time(),
                                "http": {"response": {"status": 200}},
                            }
                        ),
                    },
                    {
                        "Id": str(uuid.uuid4()),
                        "Document": json.dumps(
                            {
                                "name": str(uuid.uuid4()),
                                "start_time": time.time(),
                                "end_time": time.time(),
                                "http": {"response": {"status": 200}},
                                "subsegments": [
                                    {
                                        "Id": str(uuid.uuid4()),
                                        "name": str(uuid.uuid4()),
                                        "start_time": time.time(),
                                        "end_time": time.time(),
                                        "http": {"response": {"status": 200}},
                                    }
                                ],
                            }
                        ),
                    },
                ],
            }
        )


class TestXRayTraceConsoleMapper(AbstraceXRayTraceMapperTest):
    def test_console_mapper(self):
        console_mapper = XRayTraceConsoleMapper()
        mapped_event = console_mapper.map(self.trace_event)

        self.assertTrue(isinstance(mapped_event, XRayTraceEvent))

        self.assertTrue(
            f"New XRay Event with id ({self.trace_event.id}) and duration ({self.trace_event.duration:.3f}s)"
            in mapped_event.message
        )

        self.validate_segments(self.trace_event.segments, mapped_event.message)

    def validate_segments(self, segments, message):
        for segment in segments:

            if segment.http_status:
                self.assertTrue(
                    f" - {segment.get_duration():.3f}s - {segment.name} [HTTP: {segment.http_status}]" in message
                )
            else:
                self.assertTrue(f" - {segment.get_duration():.3f}s - {segment.name}" in message)
            self.validate_segments(segments.sub_segments, message)


class TestXRayTraceFileMapper(AbstraceXRayTraceMapperTest):
    def test_escaped_json_will_be_dict(self):
        file_mapper = XRayTraceFileMapper()
        mapped_event = file_mapper.map(self.trace_event)

        segments = mapped_event.event.get("Segments")
        self.assertTrue(isinstance(segments, list))
        for segment in segments:
            self.assertTrue(isinstance(segment, dict))
