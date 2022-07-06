"""
Module for testing the event.py methods and classes.
"""

from enum import Enum
import threading
from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from samcli.lib.telemetry.event import Event, EventCreationError, EventTracker


class DummyEventName(Enum):
    TEST_ONE = "TestOne"
    TEST_TWO = "TestTwo"
    TEST_THREE = "TestThree"


class TestEventCreation(TestCase):
    @patch("samcli.lib.telemetry.event.Event._verify_event")
    @patch("samcli.lib.telemetry.event.EventType")
    @patch("samcli.lib.telemetry.event.EventName")
    def test_create_event_exists(self, name_mock, type_mock, verify_mock):
        name_mock.return_value = Mock(value="TestOne")
        type_mock.get_accepted_values.return_value = ["value1", "value2"]
        verify_mock.return_value = None

        test_event = Event("TestOne", "value1")

        name_mock.assert_called_once()
        self.assertEqual(test_event.event_name.value, "TestOne")
        self.assertEqual(test_event.event_value, "value1")
        self.assertEqual(test_event.thread_id, threading.get_ident())  # Should be on the same thread

    @patch("samcli.lib.telemetry.event.EventType")
    @patch("samcli.lib.telemetry.event.EventName")
    @patch("samcli.lib.telemetry.event.Event._get_event_names")
    def test_create_event_value_doesnt_exist(self, name_getter_mock, name_mock, type_mock):
        name_getter_mock.return_value = ["TestOne"]
        name_mock.return_value = Mock(value="TestOne")
        type_mock.get_accepted_values.return_value = ["value1", "value2"]

        with self.assertRaises(EventCreationError) as e:
            Event("TestOne", "value3")

        self.assertEqual(e.exception.args[0], "Event 'TestOne' does not accept value 'value3'.")

    def test_create_event_name_doesnt_exist(self):
        with self.assertRaises(EventCreationError) as e:
            Event("SomeEventThatDoesn'tExist", "value1")

        self.assertEqual(e.exception.args[0], "Event 'SomeEventThatDoesn'tExist' does not exist.")

    @patch("samcli.lib.telemetry.event.Event._verify_event")
    @patch("samcli.lib.telemetry.event.EventType")
    @patch("samcli.lib.telemetry.event.EventName")
    def test_event_to_json(self, name_mock, type_mock, verify_mock):
        name_mock.return_value = Mock(value="Testing")
        type_mock.get_accepted_values.return_value = ["value1"]
        verify_mock.return_value = None

        test_event = Event("Testing", "value1")

        self.assertEqual(
            test_event.to_json(),
            {"event_name": "Testing", "event_value": "value1", "thread_id": threading.get_ident(), "timestamp": ANY},
        )


class TestEventTracker(TestCase):
    @patch("samcli.lib.telemetry.event.EventTracker._event_lock")
    @patch("samcli.lib.telemetry.event.Event")
    def test_track_event(self, event_mock, lock_mock):
        lock_mock.__enter__ = Mock()
        lock_mock.__exit__ = Mock()

        # Test that an event can be tracked
        dummy_event = Mock(event_name="Test", event_value="SomeValue", thread_id=threading.get_ident(), timestamp=ANY)
        event_mock.return_value = dummy_event

        EventTracker.track_event("Test", "SomeValue")

        self.assertEqual(len(EventTracker._events), 1)
        self.assertEqual(EventTracker._events[0], dummy_event)
        lock_mock.__enter__.assert_called()  # Lock should have been accessed
        lock_mock.__exit__.assert_called()
        lock_mock.__enter__.reset_mock()
        lock_mock.__exit__.reset_mock()

        # Test that the Event list will be cleared
        EventTracker.clear_trackers()

        self.assertEqual(len(EventTracker._events), 0)
        lock_mock.__enter__.assert_called()  # Lock should have been accessed
        lock_mock.__exit__.assert_called()
