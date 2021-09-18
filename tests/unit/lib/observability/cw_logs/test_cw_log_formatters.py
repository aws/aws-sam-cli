import json
from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent
from samcli.lib.observability.cw_logs.cw_log_formatters import (
    CWPrettyPrintFormatter,
    CWColorizeErrorsFormatter,
    CWKeywordHighlighterFormatter,
    CWJsonFormatter,
    CWAddNewLineIfItDoesntExist,
    CWLogEventJSONMapper,
)


class TestCWPrettyPrintFormatter(TestCase):
    def setUp(self):
        self.colored = Mock()
        self.pretty_print_formatter = CWPrettyPrintFormatter(self.colored)
        self.group_name = "group name"
        self.stream_name = "stream name"
        self.message = "message"
        self.event_dict = {"timestamp": 1, "message": self.message, "logStreamName": self.stream_name}

    def test_must_serialize_event(self):
        colored_timestamp = "colored timestamp"
        colored_stream_name = "colored stream name"
        self.colored.yellow.return_value = colored_timestamp
        self.colored.cyan.return_value = colored_stream_name

        event = CWLogEvent(self.group_name, self.event_dict)

        expected = " ".join([colored_stream_name, colored_timestamp, self.message])
        result = self.pretty_print_formatter.map(event)

        self.assertEqual(expected, result.message)
        self.colored.yellow.has_calls()
        self.colored.cyan.assert_called_with(self.stream_name)


class TestCWColorizeErrorsFormatter(TestCase):
    def setUp(self):
        self.colored = Mock()
        self.formatter = CWColorizeErrorsFormatter(self.colored)

    @parameterized.expand(
        [
            "Task timed out",
            "Something happened. Task timed out. Something else happend",
            "Process exited before completing request",
        ]
    )
    def test_must_color_crash_messages(self, input_msg):
        color_result = "colored messaage"
        self.colored.red.return_value = color_result
        event = CWLogEvent("group_name", {"message": input_msg})

        result = self.formatter.map(event)
        self.assertEqual(result.message, color_result)
        self.colored.red.assert_called_with(input_msg)

    def test_must_ignore_other_messages(self):
        event = CWLogEvent("group_name", {"message": "some msg"})

        result = self.formatter.map(event)
        self.assertEqual(result.message, "some msg")
        self.colored.red.assert_not_called()


class CWCWKeywordHighlighterFormatter(TestCase):
    def setUp(self):
        self.colored = Mock()

    def test_must_highlight_all_keywords(self):
        input_msg = "this keyword some keyword other keyword"
        keyword = "keyword"
        color_result = "colored"
        expected_msg = "this colored some colored other colored"

        formatter = CWKeywordHighlighterFormatter(self.colored, keyword)

        self.colored.underline.return_value = color_result
        event = CWLogEvent("group_name", {"message": input_msg})

        result = formatter.map(event)
        self.assertEqual(result.message, expected_msg)
        self.colored.underline.assert_called_with(keyword)

    def test_must_ignore_if_keyword_is_absent(self):
        input_msg = "this keyword some keyword other keyword"
        event = CWLogEvent("group_name", {"message": input_msg})

        formatter = CWKeywordHighlighterFormatter(self.colored)

        result = formatter.map(event)
        self.assertEqual(result.message, input_msg)
        self.colored.underline.assert_not_called()


class TestCWJsonFormatter(TestCase):
    def setUp(self):
        self.formatter = CWJsonFormatter()

    def test_must_pretty_print_json(self):
        data = {"a": "b"}
        input_msg = '{"a": "b"}'
        expected_msg = json.dumps(data, indent=2)

        event = CWLogEvent("group_name", {"message": input_msg})

        result = self.formatter.map(event)
        self.assertEqual(result.message, expected_msg)

    @parameterized.expand(["this is not json", '{"not a valid json"}'])
    def test_ignore_non_json(self, input_msg):

        event = CWLogEvent("group_name", {"message": input_msg})

        result = self.formatter.map(event)
        self.assertEqual(result.message, input_msg)


class TestCWAddNewLineIfItDoesntExist(TestCase):
    def setUp(self) -> None:
        self.formatter = CWAddNewLineIfItDoesntExist()

    @parameterized.expand(
        [
            (CWLogEvent("log_group", {"message": "input"}),),
            (CWLogEvent("log_group", {"message": "input\n"}),),
        ]
    )
    def test_cw_log_event(self, log_event):
        mapped_event = self.formatter.map(log_event)
        self.assertEqual(mapped_event.message, "input\n")

    @parameterized.expand(
        [
            ("input",),
            ("input\n",),
        ]
    )
    def test_str_event(self, str_event):
        mapped_event = self.formatter.map(str_event)
        self.assertEqual(mapped_event, "input\n")

    @parameterized.expand(
        [
            ({"some": "dict"},),
            (5,),
        ]
    )
    def test_other_events(self, event):
        mapped_event = self.formatter.map(event)
        self.assertEqual(mapped_event, event)


class TestCWLogEventJSONMapper(TestCase):
    def test_mapper(self):
        given_event = CWLogEvent("log_group", {"message": "input"})
        mapper = CWLogEventJSONMapper()

        mapped_event = mapper.map(given_event)
        self.assertEqual(mapped_event.message, json.dumps(given_event.event))
