
from unittest import TestCase

from samcli.lib.logs.event import LogEvent


class TestLogEvent(TestCase):

    def setUp(self):
        self.group_name = "log group name"
        self.stream_name = "stream name"
        self.message = "message"
        self.timestamp = 1530882594000
        self.timestamp_str = "2018-07-06T13:09:54"

    def test_must_extract_fields_from_event(self):
        event = LogEvent(self.group_name, {
            "timestamp": self.timestamp,
            "logStreamName": self.stream_name,
            "message": self.message
        })

        self.assertEquals(event.log_group_name, self.group_name)
        self.assertEquals(event.log_stream_name, self.stream_name)
        self.assertEquals(event.message, self.message)
        self.assertEquals(self.timestamp_str, event.timestamp)

    def test_must_ignore_if_some_fields_are_empty(self):
        event = LogEvent(self.group_name, {
            "logStreamName": "stream name"
        })

        self.assertEquals(event.log_group_name, self.group_name)
        self.assertEquals(event.log_stream_name, self.stream_name)
        self.assertEquals(event.message, '')
        self.assertIsNone(event.timestamp)

    def test_must_ignore_if_event_is_empty(self):
        event = LogEvent(self.group_name, {})

        self.assertEquals(event.log_group_name, self.group_name)
        self.assertIsNone(event.log_stream_name)
        self.assertIsNone(event.message)
        self.assertIsNone(event.timestamp)

    def test_check_for_equality(self):
        event = LogEvent(self.group_name, {
            "timestamp": self.timestamp,
            "logStreamName": self.stream_name,
            "message": self.message
        })

        other = LogEvent(self.group_name, {
            "timestamp": self.timestamp,
            "logStreamName": self.stream_name,
            "message": self.message
        })

        self.assertEquals(event, other)

    def test_check_for_equality_with_other_data_types(self):
        event = LogEvent(self.group_name, {})
        other = "this is not an event"

        self.assertNotEquals(event, other)
