"""
Module for testing the event.py methods and classes.
"""

from enum import Enum
from unittest import TestCase
from unittest.mock import Mock, patch

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


class TestEventTracker(TestCase):
    @patch("samcli.lib.telemetry.event.Event")
    def test_track_event(self, event_mock):
        # Test that an event can be tracked
        dummy_event = Mock(event_name="Test", event_value="SomeValue")
        event_mock.return_value = dummy_event

        EventTracker.track_event("Test", "SomeValue")

        self.assertEqual(len(EventTracker._events), 1)
        self.assertEqual(EventTracker._events[0], dummy_event)

        # Test that the Event list will be cleared
        EventTracker.clear_trackers()

        self.assertEqual(len(EventTracker._events), 0)
