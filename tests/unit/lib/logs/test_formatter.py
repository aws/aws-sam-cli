
import json

from unittest import TestCase
from mock import Mock, patch, call
from nose_parameterized import parameterized

from samcli.lib.logs.formatter import LogsFormatter, LambdaLogMsgFormatters, KeywordHighlighter, JSONMsgFormatter
from samcli.lib.logs.event import LogEvent


class TestLogsFormatter_pretty_print_event(TestCase):

    def setUp(self):
        self.colored_mock = Mock()
        self.group_name = "group name"
        self.stream_name = "stream name"
        self.message = "message"
        self.event_dict = {
            "timestamp": 1,
            "message": self.message,
            "logStreamName": self.stream_name
        }

    def test_must_serialize_event(self):
        colored_timestamp = "colored timestamp"
        colored_stream_name = "colored stream name"
        self.colored_mock.yellow.return_value = colored_timestamp
        self.colored_mock.cyan.return_value = colored_stream_name

        event = LogEvent(self.group_name, self.event_dict)

        expected = ' '.join([colored_stream_name, colored_timestamp, self.message])
        result = LogsFormatter._pretty_print_event(event, self.colored_mock)

        self.assertEquals(expected, result)
        self.colored_mock.yellow.has_calls()
        self.colored_mock.cyan.assert_called_with(self.stream_name)


def _passthru_formatter(event, colored):
    return event


class TestLogsFormatter_do_format(TestCase):

    def setUp(self):
        self.colored_mock = Mock()

        # Set formatter chain method to return the input unaltered.
        self.chain_method1 = Mock(wraps=_passthru_formatter)
        self.chain_method2 = Mock(wraps=_passthru_formatter)
        self.chain_method3 = Mock(wraps=_passthru_formatter)

        self.formatter_chain = [self.chain_method1, self.chain_method2, self.chain_method3]

    @patch.object(LogsFormatter, "_pretty_print_event", wraps=_passthru_formatter)
    def test_must_map_formatters_sequentially(self, pretty_print_mock):

        events_iterable = [1, 2, 3]
        expected_result = [1, 2, 3]
        expected_call_order = [
            call(1, colored=self.colored_mock),
            call(2, colored=self.colored_mock),
            call(3, colored=self.colored_mock)
        ]

        formatter = LogsFormatter(self.colored_mock, self.formatter_chain)

        result_iterable = formatter.do_format(events_iterable)
        self.assertEquals(list(result_iterable), expected_result)

        self.chain_method1.assert_has_calls(expected_call_order)
        self.chain_method2.assert_has_calls(expected_call_order)
        self.chain_method3.assert_has_calls(expected_call_order)
        pretty_print_mock.assert_has_calls(expected_call_order)  # Pretty Printer must always be called

    @patch.object(LogsFormatter, "_pretty_print_event", wraps=_passthru_formatter)
    def test_must_work_without_formatter_chain(self, pretty_print_mock):

        events_iterable = [1, 2, 3]
        expected_result = [1, 2, 3]
        expected_call_order = [
            call(1, colored=self.colored_mock),
            call(2, colored=self.colored_mock),
            call(3, colored=self.colored_mock)
        ]

        # No formatter chain.
        formatter = LogsFormatter(self.colored_mock)

        result_iterable = formatter.do_format(events_iterable)
        self.assertEquals(list(result_iterable), expected_result)

        # Pretty Print is always called, even if there are no other formatters in the chain.
        pretty_print_mock.assert_has_calls(expected_call_order)
        self.chain_method1.assert_not_called()
        self.chain_method2.assert_not_called()
        self.chain_method3.assert_not_called()


class TestLambdaLogMsgFormatters_colorize_crashes(TestCase):

    @parameterized.expand([
        "Task timed out",
        "Something happened. Task timed out. Something else happend",
        "Process exited before completing request"
    ])
    def test_must_color_crash_messages(self, input_msg):
        color_result = "colored messaage"
        colored = Mock()
        colored.red.return_value = color_result
        event = LogEvent("group_name", {"message": input_msg})

        result = LambdaLogMsgFormatters.colorize_errors(event, colored)
        self.assertEquals(result.message, color_result)
        colored.red.assert_called_with(input_msg)

    def test_must_ignore_other_messages(self):
        colored = Mock()
        event = LogEvent("group_name", {"message": "some msg"})

        result = LambdaLogMsgFormatters.colorize_errors(event, colored)
        self.assertEquals(result.message, "some msg")
        colored.red.assert_not_called()


class TestKeywordHighlight_highlight_keyword(TestCase):

    def test_must_highlight_all_keywords(self):
        input_msg = "this keyword some keyword other keyword"
        keyword = "keyword"
        color_result = "colored"
        expected_msg = "this colored some colored other colored"

        colored = Mock()
        colored.underline.return_value = color_result
        event = LogEvent("group_name", {"message": input_msg})

        result = KeywordHighlighter(keyword).highlight_keywords(event, colored)
        self.assertEquals(result.message, expected_msg)
        colored.underline.assert_called_with(keyword)

    def test_must_ignore_if_keyword_is_absent(self):
        colored = Mock()
        input_msg = "this keyword some keyword other keyword"
        event = LogEvent("group_name", {"message": input_msg})

        result = KeywordHighlighter().highlight_keywords(event, colored)
        self.assertEquals(result.message, input_msg)
        colored.underline.assert_not_called()


class TestJSONMsgFormatter_format_json(TestCase):

    def test_must_pretty_print_json(self):
        data = {"a": "b"}
        input_msg = '{"a": "b"}'
        expected_msg = json.dumps(data, indent=2)

        event = LogEvent("group_name", {"message": input_msg})

        result = JSONMsgFormatter.format_json(event, None)
        self.assertEquals(result.message, expected_msg)

    @parameterized.expand([
        "this is not json",
        '{"not a valid json"}',
    ])
    def test_ignore_non_json(self, input_msg):

        event = LogEvent("group_name", {"message": input_msg})

        result = JSONMsgFormatter.format_json(event, None)
        self.assertEquals(result.message, input_msg)
