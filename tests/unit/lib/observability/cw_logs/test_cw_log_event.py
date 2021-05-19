from unittest import TestCase

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent


class TestCWLogEvent(TestCase):
    def setUp(self):
        self.group_name = "log group name"
        self.stream_name = "stream name"
        self.message = "message"
        self.timestamp = 1530882594000
        self.timestamp_str = "2018-07-06T13:09:54"

    def test_must_extract_fields_from_event(self):
        event = CWLogEvent(
            self.group_name, {"timestamp": self.timestamp, "logStreamName": self.stream_name, "message": self.message}
        )

        self.assertEqual(event.cw_log_group, self.group_name)
        self.assertEqual(event.log_stream_name, self.stream_name)
        self.assertEqual(event.message, self.message)
        self.assertEqual(self.timestamp, event.timestamp)

    def test_must_ignore_if_some_fields_are_empty(self):
        event = CWLogEvent(self.group_name, {"logStreamName": "stream name"})

        self.assertEqual(event.cw_log_group, self.group_name)
        self.assertEqual(event.log_stream_name, self.stream_name)
        self.assertEqual(event.message, "")
        self.assertEqual(event.timestamp, 0)

    def test_must_ignore_if_event_is_empty(self):
        event = CWLogEvent(self.group_name, {})

        self.assertEqual(event.cw_log_group, self.group_name)
        self.assertEqual(event.log_stream_name, "")
        self.assertEqual(event.message, "")
        self.assertEqual(event.timestamp, 0)

    def test_check_for_equality(self):
        event = CWLogEvent(
            self.group_name, {"timestamp": self.timestamp, "logStreamName": self.stream_name, "message": self.message}
        )

        other = CWLogEvent(
            self.group_name, {"timestamp": self.timestamp, "logStreamName": self.stream_name, "message": self.message}
        )

        self.assertEqual(event, other)

    def test_check_for_inequality(self):
        event = CWLogEvent(
            self.group_name,
            {"timestamp": self.timestamp + 1, "logStreamName": self.stream_name, "message": self.message},
        )

        other = CWLogEvent(
            self.group_name, {"timestamp": self.timestamp, "logStreamName": self.stream_name, "message": self.message}
        )

        self.assertNotEqual(event, other)

    def test_check_for_equality_with_other_data_types(self):
        event = CWLogEvent(self.group_name, {})
        other = "this is not an event"

        self.assertNotEqual(event, other)
