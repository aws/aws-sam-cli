import json
import time
import uuid
import logging
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from samcli.lib.observability.xray_traces.xray_event_mappers import (
    XRayTraceConsoleMapper,
    XRayTraceJSONMapper,
    XRayServiceGraphConsoleMapper,
    XRayServiceGraphJSONMapper,
)
from samcli.lib.observability.xray_traces.xray_events import XRayTraceEvent, XRayServiceGraphEvent
from samcli.lib.utils.time import to_utc, utc_to_timestamp, timestamp_to_iso

LOG = logging.getLogger()
logging.basicConfig()


class AbstraceXRayTraceMapperTest(TestCase):
    def setUp(self):
        self.trace_event = XRayTraceEvent(
            {
                "Id": str(uuid.uuid4()),
                "Duration": 2.1,
                "Segments": [
                    {
                        "Id": str(uuid.uuid4()),
                        "Document": json.dumps(
                            {
                                "name": str(uuid.uuid4()),
                                "start_time": 1634603579.27,  # 2021-10-18T17:32:59.270000
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
            },
            1,
        )


class TestXRayTraceConsoleMapper(AbstraceXRayTraceMapperTest):
    def test_console_mapper(self):
        with patch("samcli.lib.observability.xray_traces.xray_event_mappers.datetime") as fromtimestamp_mock:
            fromtimestamp_mock.side_effect = lambda *args, **kw: datetime(*args, **kw)
            fromtimestamp_mock.fromtimestamp.return_value = datetime(2021, 10, 18, 17, 32, 59, 270000)

            console_mapper = XRayTraceConsoleMapper()
            mapped_event = console_mapper.map(self.trace_event)

            self.assertTrue(isinstance(mapped_event, XRayTraceEvent))

            event_timestamp = "2021-10-18T17:32:59.270000"
            LOG.info(mapped_event.message)
            self.assertTrue(
                f"XRay Event [revision 1] at ({event_timestamp}) with id ({self.trace_event.id}) and duration ({self.trace_event.duration:.3f}s)"
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
            self.validate_segments(segment.sub_segments, message)


class TestXRayTraceJSONMapper(AbstraceXRayTraceMapperTest):
    def test_escaped_json_will_be_dict(self):
        json_mapper = XRayTraceJSONMapper()
        mapped_event = json_mapper.map(self.trace_event)

        segments = mapped_event.event.get("Segments")
        self.assertTrue(isinstance(segments, list))
        for segment in segments:
            self.assertTrue(isinstance(segment, dict))
        self.assertEqual(mapped_event.event, json.loads(mapped_event.message))


class AbstractXRayServiceGraphMapperTest(TestCase):
    def setUp(self):
        self.service_graph_event = XRayServiceGraphEvent(
            {
                "StartTime": datetime(2015, 1, 1),
                "EndTime": datetime(2015, 1, 1),
                "Services": [
                    {
                        "ReferenceId": 123,
                        "Name": "string",
                        "Root": True | False,
                        "Type": "string",
                        "StartTime": datetime(2015, 1, 1),
                        "EndTime": datetime(2015, 1, 1),
                        "Edges": [
                            {
                                "ReferenceId": 123,
                                "StartTime": datetime(2015, 1, 1),
                                "EndTime": datetime(2015, 1, 1),
                            },
                        ],
                        "SummaryStatistics": {
                            "OkCount": 123,
                            "ErrorStatistics": {"TotalCount": 123},
                            "FaultStatistics": {"TotalCount": 123},
                            "TotalCount": 123,
                            "TotalResponseTime": 123.0,
                        },
                    },
                ],
            }
        )


class TestXRayServiceGraphConsoleMapper(AbstractXRayServiceGraphMapperTest):
    def test_console_mapper(self):
        console_mapper = XRayServiceGraphConsoleMapper()
        mapped_event = console_mapper.map(self.service_graph_event)

        self.assertTrue(isinstance(mapped_event, XRayServiceGraphEvent))

        self.assertTrue(f"\nNew XRay Service Graph" in mapped_event.message)
        self.assertTrue(f"\n  Start time: {self.service_graph_event.start_time}" in mapped_event.message)
        self.assertTrue(f"\n  End time: {self.service_graph_event.end_time}" in mapped_event.message)

        self.validate_services(self.service_graph_event.services, mapped_event.message)

    def validate_services(self, services, message):
        for service in services:
            self.assertTrue(f"Reference Id: {service.id}" in message)
            if service.is_root:
                self.assertTrue("(Root)" in message)
            else:
                self.assertFalse("(Root)" in message)
            self.assertTrue(f" {service.type} - {service.name}" in message)
            edg_id_str = str(service.edge_ids)
            self.assertTrue(f"Edges: {edg_id_str}" in message)
            self.validate_summary_statistics(service, message)

    def validate_summary_statistics(self, service, message):
        self.assertTrue("Summary_statistics:" in message)
        self.assertTrue(f"total requests: {service.total_count}" in message)
        self.assertTrue(f"ok count(2XX): {service.ok_count}" in message)
        self.assertTrue(f"error count(4XX): {service.error_count}" in message)
        self.assertTrue(f"fault count(5XX): {service.fault_count}" in message)
        self.assertTrue(f"total response time: {service.response_time}" in message)


class TestXRayServiceGraphFileMapper(AbstractXRayServiceGraphMapperTest):
    def test_datetime_object_convert_to_iso_string(self):
        actual_datetime = datetime(2015, 1, 1)
        json_mapper = XRayServiceGraphJSONMapper()
        mapped_event = json_mapper.map(self.service_graph_event)
        mapped_dict = mapped_event.event

        self.validate_start_and_end_time(actual_datetime, mapped_dict)
        services = mapped_dict.get("Services", [])
        for service in services:
            self.validate_start_and_end_time(actual_datetime, service)
            edges = service.get("Edges", [])
            for edge in edges:
                self.validate_start_and_end_time(actual_datetime, edge)
        self.assertEqual(mapped_event.event, json.loads(mapped_event.message))

    def validate_start_and_end_time(self, datetime_obj, event_dict):
        self.validate_datetime_object_to_iso_string("StartTime", datetime_obj, event_dict)
        self.validate_datetime_object_to_iso_string("EndTime", datetime_obj, event_dict)

    def validate_datetime_object_to_iso_string(self, datetime_key, datetime_obj, event_dict):
        datetime_str = event_dict.get(datetime_key)
        self.assertTrue(isinstance(datetime_str, str))
        expected_utc_datetime = to_utc(datetime_obj)
        expected_timestamp = utc_to_timestamp(expected_utc_datetime)
        expected_iso_str = timestamp_to_iso(expected_timestamp)
        self.assertEqual(datetime_str, expected_iso_str)
