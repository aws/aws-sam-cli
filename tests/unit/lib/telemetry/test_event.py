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
            {"event_name": "Testing", "event_value": "value1", "thread_id": threading.get_ident(), "time_stamp": ANY},
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

    @patch("samcli.lib.telemetry.event.Telemetry")
    def test_events_get_sent(self, telemetry_mock):
        # Create fake emit to capture tracked events
        dummy_telemetry = Mock()
        tracked_events = []
        mock_emit = lambda x: tracked_events.append(x)
        dummy_telemetry.emit.return_value = None
        dummy_telemetry.emit.side_effect = mock_emit
        telemetry_mock.return_value = dummy_telemetry

        # Verify that no events are sent if tracker is empty
        EventTracker.send_events()

        self.assertEqual(tracked_events, [])  # No events should have been collected
        dummy_telemetry.emit.assert_not_called()  # Nothing should have been sent (empty list)

        # Verify that events get sent when they exist in tracker
        dummy_event = Mock(
            event_name=Mock(value="Test"), event_value="SomeValue", thread_id=threading.get_ident(), time_stamp=ANY
        )
        dummy_event.to_json.return_value = Event.to_json(dummy_event)
        EventTracker._events.append(dummy_event)

        EventTracker.send_events()

        dummy_telemetry.emit.assert_called()
        self.assertEqual(len(tracked_events), 1)  # The list of metrics (1) is copied into tracked_events
        metric_data = tracked_events[0].get_data()
        expected_data = {
            "requestId": ANY,
            "installationId": ANY,
            "sessionId": ANY,
            "executionEnvironment": ANY,
            "ci": ANY,
            "pyversion": ANY,
            "samcliVersion": ANY,
            "metricSpecificAttributes": {
                "events": [
                    {
                        "event_name": "Test",
                        "event_value": "SomeValue",
                        "thread_id": ANY,
                        "time_stamp": ANY,
                    }
                ]
            },
        }
        print(metric_data)
        self.assertEqual(len(metric_data["metricSpecificAttributes"]["events"]), 1)  # There is one event captured
        self.assertEqual(metric_data, expected_data)
        self.assertEqual(len(EventTracker._events), 0)  # Events should have been sent and cleared

    @patch(
        "samcli.lib.telemetry.event.EventTracker.send_events",
        return_value=None,
        side_effect=EventTracker.clear_trackers,
    )
    @patch("samcli.lib.telemetry.event.Event")
    def test_send_events_when_capacity_reached(self, event_mock, send_mock):
        # Create dummy Event creator to bypass verification
        def make_mock_event(name, value):
            dummy = Mock(event_name=Mock(value=name), event_value=value, thread_id=ANY, time_stamp=ANY)
            dummy.to_json.return_value = Event.to_json(dummy)
            return dummy

        event_mock.return_value = make_mock_event

        # Fill EventTracker with almost enough events to reach capacity
        for i in range(EventTracker.MAX_EVENTS - 1):
            EventTracker.track_event(f"Name{i}", f"Value{i}")

        send_mock.assert_not_called()
        self.assertEqual(len(EventTracker._events), EventTracker.MAX_EVENTS - 1)

        # Add one more event to trigger sending all events
        EventTracker.track_event("TheStrawThat", "BreaksTheCamel'sBack")

        send_mock.assert_called()
        self.assertEqual(len(EventTracker._events), 0)  # List of events is reset upon hitting capacity
