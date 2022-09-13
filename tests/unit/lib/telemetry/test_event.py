"""
Module for testing the event.py methods and classes.
"""

from enum import Enum
import threading
from typing import List, Tuple
from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from samcli.lib.telemetry.event import Event, EventCreationError, EventTracker, track_long_event


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
    def setUp(self):
        EventTracker.clear_trackers()

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
        emitted_events = []
        mock_emit = lambda x: emitted_events.append(x)
        dummy_telemetry.emit.return_value = None
        dummy_telemetry.emit.side_effect = mock_emit
        telemetry_mock.return_value = dummy_telemetry

        # Verify that no events are sent if tracker is empty
        # Note we are using the in-line version of the method, as the regular send_events will
        # simply call this method in a new thread
        EventTracker._send_events_in_thread()

        self.assertEqual(emitted_events, [])  # No events should have been collected
        dummy_telemetry.emit.assert_not_called()  # Nothing should have been sent (empty list)

        # Verify that events get sent when they exist in tracker
        dummy_event = Mock(
            event_name=Mock(value="Test"), event_value="SomeValue", thread_id=threading.get_ident(), time_stamp=ANY
        )
        dummy_event.to_json.return_value = Event.to_json(dummy_event)
        EventTracker._events.append(dummy_event)

        EventTracker._send_events_in_thread()

        dummy_telemetry.emit.assert_called()
        self.assertEqual(len(emitted_events), 1)  # The list of metrics (1) is copied into emitted_events
        metric_data = emitted_events[0].get_data()
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
        self.assertEqual(len(metric_data["metricSpecificAttributes"]["events"]), 1)  # There is one event captured
        self.assertEqual(metric_data, expected_data)
        self.assertEqual(len(EventTracker._events), 0)  # Events should have been sent and cleared

    @patch(
        "samcli.lib.telemetry.event.EventTracker.send_events",
        return_value=None,
    )
    @patch("samcli.lib.telemetry.event.Event")
    def test_track_event_events_sent_when_capacity_reached(self, event_mock, send_mock):
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


class TestTrackLongEvent(TestCase):
    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.event.EventTracker.track_event")
    @patch("samcli.lib.telemetry.event.Event", return_value=None)
    def test_long_event_is_tracked(self, event_mock, track_mock, send_mock):
        mock_tracker = {}
        mock_tracker["tracked_events"]: List[Tuple[str, str]] = []  # Tuple to bypass Event verification
        mock_tracker["emitted_events"]: List[Tuple[str, str]] = []

        def mock_track(name, value):
            mock_tracker["tracked_events"].append((name, value))

        def mock_send():
            mock_tracker["emitted_events"] = mock_tracker["tracked_events"]
            mock_tracker["tracked_events"] = []  # Mimic clear_trackers()

        track_mock.side_effect = mock_track
        send_mock.side_effect = mock_send

        @track_long_event("StartEvent", "StartValue", "EndEvent", "EndValue")
        def func():
            self.assertEqual(len(mock_tracker["tracked_events"]), 1, "Starting event not tracked.")
            self.assertIn(("StartEvent", "StartValue"), mock_tracker["tracked_events"], "Incorrect starting event.")

        func()

        self.assertEqual(len(mock_tracker["tracked_events"]), 0, "Tracked events not reset; send_events not called.")
        self.assertEqual(len(mock_tracker["emitted_events"]), 2, "Unexpected number of emitted events.")
        self.assertIn(("StartEvent", "StartValue"), mock_tracker["emitted_events"], "Starting event not tracked.")
        self.assertIn(("EndEvent", "EndValue"), mock_tracker["emitted_events"], "Ending event not tracked.")

    @patch("samcli.lib.telemetry.event.EventTracker.send_events")
    @patch("samcli.lib.telemetry.event.EventTracker.track_event")
    def test_nothing_tracked_if_invalid_events(self, track_mock, send_mock):
        mock_tracker = {}
        mock_tracker["tracked_events"]: List[Tuple[str, str]] = []  # Tuple to bypass Event verification
        mock_tracker["emitted_events"]: List[Tuple[str, str]] = []

        def mock_track(name, value):
            mock_tracker["tracked_events"].append((name, value))

        def mock_send():
            mock_tracker["emitted_events"] = mock_tracker["tracked_events"]
            mock_tracker["tracked_events"] = []  # Mimic clear_trackers()

        track_mock.side_effect = mock_track
        send_mock.side_effect = mock_send

        @track_long_event("DefinitelyNotARealEvent", "Nope", "ThisEventDoesntExist", "NuhUh")
        def func():
            self.assertEqual(len(mock_tracker["tracked_events"]), 0, "Events should not have been tracked.")

        func()

        self.assertEqual(len(mock_tracker["tracked_events"]), 0, "Events should not have been tracked.")
        self.assertEqual(len(mock_tracker["emitted_events"]), 0, "Events should not have been emitted.")
        track_mock.assert_not_called()  # Tracker should not have been called
        send_mock.assert_not_called()  # Sender should not have been called
