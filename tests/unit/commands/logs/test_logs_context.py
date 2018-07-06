
from unittest import TestCase
from mock import Mock, patch, ANY, mock_open

from samcli.commands.logs.logs_context import LogsCommandContext
from samcli.commands.exceptions import UserException

class TestLogsCommandContext(TestCase):

    def setUp(self):
        self.function_name = "name"
        self.stack_name = "stack name"
        self.filter_pattern = "filter"
        self.tailing = True
        self.start_time = "start"
        self.end_time = "end"
        self.output_file = "somefile"

        self.context = LogsCommandContext(self.function_name,
                                          stack_name=self.stack_name,
                                          filter_pattern=self.filter_pattern,
                                          tailing=self.tailing,
                                          start_time=self.start_time,
                                          end_time=self.end_time,
                                          output_file=self.output_file)

    def test_basic_properties(self):
        self.assertEqual(self.context.filter_pattern, self.filter_pattern)
        self.assertIsNone(self.context.output_file_handle)  # before setting context handle will be null

    @patch("samcli.commands.logs.logs_context.LogsFetcher")
    def test_fetcher_property(self, LogsFetcherMock):
        LogsFetcherMock.return_value = Mock()

        self.assertEqual(
            self.context.fetcher,
            LogsFetcherMock.return_value
        )
        LogsFetcherMock.assert_called_with(self.context._logs_client)

    @patch("samcli.commands.logs.logs_context.Colored")
    def test_colored_property(self, ColoredMock):
        ColoredMock.return_value = Mock()

        self.assertEqual(
            self.context.colored,
            ColoredMock.return_value
        )
        ColoredMock.assert_called_with(colorize=False)

    @patch("samcli.commands.logs.logs_context.Colored")
    def test_colored_property_without_output_file(self, ColoredMock):
        ColoredMock.return_value = Mock()

        # Remove the output file. It means we are printing to Terminal. Hence set the color
        self.context._output_file = None

        self.assertEqual(
            self.context.colored,
            ColoredMock.return_value
        )
        ColoredMock.assert_called_with(colorize=True)  # Must enable colors

    @patch("samcli.commands.logs.logs_context.LogsFormatter")
    @patch("samcli.commands.logs.logs_context.Colored")
    def test_formatter_property(self, ColoredMock, LogsFormatterMock):
        LogsFormatterMock.return_value = Mock()
        ColoredMock.return_value = Mock()

        self.assertEqual(
            self.context.formatter,
            LogsFormatterMock.return_value
        )
        LogsFormatterMock.assert_called_with(ColoredMock.return_value,
                                             ANY)

    @patch("samcli.commands.logs.logs_context.LogGroupProvider")
    def test_log_group_name_property(self, LogGroupProviderMock):
        group = "groupname"
        LogGroupProviderMock.for_lambda_function.return_value = group

        self.assertEqual(
            self.context.log_group_name,
            group
        )

        LogGroupProviderMock.for_lambda_function.assert_called_with(self.function_name)

    def test_start_time_property(self):
        self.context._parse_time = Mock()
        self.context._parse_time.return_value = "foo"

        self.assertEquals(self.context.start_time, "foo")

    def test_end_time_property(self):
        self.context._parse_time = Mock()
        self.context._parse_time.return_value = "foo"

        self.assertEquals(self.context.end_time, "foo")

    @patch('samcli.commands.logs.logs_context.parse_date')
    @patch('samcli.commands.logs.logs_context.to_utc')
    def test_parse_time(self, to_utc_mock, parse_date_mock):
        input = "some time"
        parsed_result = "parsed"
        expected = "bar"
        parse_date_mock.return_value = parsed_result
        to_utc_mock.return_value = expected

        actual = LogsCommandContext._parse_time(input, "some prop")
        self.assertEquals(actual, expected)

        parse_date_mock.assert_called_with(input)
        to_utc_mock.assert_called_with(parsed_result)

    @patch('samcli.commands.logs.logs_context.parse_date')
    def test_parse_time_raises_exception(self, parse_date_mock):
        input = "some time"
        parsed_result = None
        parse_date_mock.return_value = parsed_result

        with self.assertRaises(UserException) as ctx:
            LogsCommandContext._parse_time(input, "some prop")

        self.assertEquals(str(ctx.exception),
                          "Unable to parse the time provided by 'some prop'")

    def test_parse_time_empty_time(self):
        result = LogsCommandContext._parse_time(None, "some prop")
        self.assertIsNone(result)

    @patch("samcli.commands.logs.logs_context.open")
    def test_setup_output_file(self, open_mock):

        open_mock.return_value = "handle"
        result = LogsCommandContext._setup_output_file(self.output_file)

        self.assertEquals(result, "handle")
        open_mock.assert_called_with(self.output_file, "wb")

    def test_setup_output_file_without_file(self):
        self.assertIsNone(LogsCommandContext._setup_output_file(None))

    @patch.object(LogsCommandContext, "_setup_output_file")
    def test_context_manager_with_output_file(self, setup_output_file_mock):
        handle = Mock()
        setup_output_file_mock.return_value = handle

        with LogsCommandContext(self.function_name,
                                stack_name=self.stack_name,
                                filter_pattern=self.filter_pattern,
                                tailing=self.tailing,
                                start_time=self.start_time,
                                end_time=self.end_time,
                                output_file=self.output_file) as context:
            self.assertEquals(context._output_file_handle, handle)

        # Context should be reset
        self.assertIsNone(self.context._output_file_handle)
        handle.close.assert_called_with()
        setup_output_file_mock.assert_called_with(self.output_file)

    @patch.object(LogsCommandContext, "_setup_output_file")
    def test_context_manager_no_output_file(self, setup_output_file_mock):
        setup_output_file_mock.return_value = None

        with LogsCommandContext(self.function_name,
                                stack_name=self.stack_name,
                                filter_pattern=self.filter_pattern,
                                tailing=self.tailing,
                                start_time=self.start_time,
                                end_time=self.end_time,
                                output_file=None) as context:
            self.assertEquals(context._output_file_handle, None)

        # Context should be reset
        setup_output_file_mock.assert_called_with(None)





