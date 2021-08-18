from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.logs.command import do_cli


class TestLogsCliCommand(TestCase):
    def setUp(self):

        self.function_name = "name"
        self.stack_name = "stack name"
        self.filter_pattern = "filter"
        self.start_time = "start"
        self.end_time = "end"

    @patch("samcli.commands.logs.logs_context.LogsCommandContext")
    def test_without_tail(self, logs_command_context_mock):
        tailing = False

        context_mock = Mock()
        logs_command_context_mock.return_value.__enter__.return_value = context_mock

        do_cli(self.function_name, self.stack_name, self.filter_pattern, tailing, self.start_time, self.end_time)

        logs_command_context_mock.assert_called_with(
            self.function_name,
            stack_name=self.stack_name,
            filter_pattern=self.filter_pattern,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        context_mock.fetcher.load_time_period.assert_called_with(
            filter_pattern=context_mock.filter_pattern,
            start_time=context_mock.start_time,
            end_time=context_mock.end_time,
        )

    @patch("samcli.commands.logs.logs_context.LogsCommandContext")
    def test_with_tailing(self, logs_command_context_mock):
        tailing = True

        context_mock = Mock()
        logs_command_context_mock.return_value.__enter__.return_value = context_mock

        do_cli(self.function_name, self.stack_name, self.filter_pattern, tailing, self.start_time, self.end_time)

        logs_command_context_mock.assert_called_with(
            self.function_name,
            stack_name=self.stack_name,
            filter_pattern=self.filter_pattern,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        context_mock.fetcher.tail.assert_called_with(
            filter_pattern=context_mock.filter_pattern, start_time=context_mock.start_time
        )
