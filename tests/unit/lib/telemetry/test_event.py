"""
Module for testing the event.py methods and classes.
"""

from enum import Enum
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.telemetry.event import Event


class DummyEventName(Enum):
    TEST_ONE = "TestOne"
    TEST_TWO = "TestTwo"
    TEST_THREE = "TestThree"


class TestEventCreation(TestCase):
    @patch("samcli.lib.telemetry.event.Event._verify_event_name")
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

    @patch("samcli.lib.telemetry.event.Event._verify_event_name")
    @patch("samcli.lib.telemetry.event.EventType")
    @patch("samcli.lib.telemetry.event.EventName")
    def test_create_event_value_doesnt_exist(self, name_mock, type_mock, verify_mock):
        name_mock.return_value = Mock(value="TestOne")
        type_mock.get_accepted_values.return_value = ["value1", "value2"]
        verify_mock.return_value = None

        with self.assertRaises(KeyError):
            Event("TestOne", "value3")

    def test_create_event_name_doesnt_exist(self):
        with self.assertRaises(NameError):
            Event("SomeEventThatDoesn'tExist", "value1")
