from unittest import TestCase
from mock import Mock, patch, call

from samcli.commands.logs.command import do_cli


class TestLogsCliCommand(TestCase):

    def setUp(self):

        self.function_name = "name"
        self.stack_name = "stack name"
        self.filter_pattern = "filter"
        self.start_time = "start"
        self.end_time = "end"

    @patch("samcli.commands.logs.command.click")
    @patch("samcli.commands.logs.command.LogsCommandContext")
    def test_without_tail(self, LogsCommandContextMock, click_mock):
        tailing = False
        events_iterable = [1, 2, 3]
        formatted_events = [4, 5, 6]

        context_mock = Mock()
        LogsCommandContextMock.return_value.__enter__.return_value = context_mock

        context_mock.fetcher.fetch.return_value = events_iterable
        context_mock.formatter.do_format.return_value = formatted_events

        do_cli(self.function_name, self.stack_name, self.filter_pattern, tailing,
               self.start_time, self.end_time)

        LogsCommandContextMock.assert_called_with(self.function_name,
                                                  stack_name=self.stack_name,
                                                  filter_pattern=self.filter_pattern,
                                                  start_time=self.start_time,
                                                  end_time=self.end_time,
                                                  output_file=None)

        context_mock.fetcher.fetch.assert_called_with(context_mock.log_group_name,
                                                      filter_pattern=context_mock.filter_pattern,
                                                      start=context_mock.start_time,
                                                      end=context_mock.end_time)

        context_mock.formatter.do_format.assert_called_with(events_iterable)
        click_mock.echo.assert_has_calls([call(v, nl=False) for v in formatted_events])

    @patch("samcli.commands.logs.command.click")
    @patch("samcli.commands.logs.command.LogsCommandContext")
    def test_with_tailing(self, LogsCommandContextMock, click_mock):
        tailing = True
        events_iterable = [1, 2, 3]
        formatted_events = [4, 5, 6]

        context_mock = Mock()
        LogsCommandContextMock.return_value.__enter__.return_value = context_mock

        context_mock.fetcher.tail.return_value = events_iterable
        context_mock.formatter.do_format.return_value = formatted_events

        do_cli(self.function_name, self.stack_name, self.filter_pattern, tailing,
               self.start_time, self.end_time)

        LogsCommandContextMock.assert_called_with(self.function_name,
                                                  stack_name=self.stack_name,
                                                  filter_pattern=self.filter_pattern,
                                                  start_time=self.start_time,
                                                  end_time=self.end_time,
                                                  output_file=None)

        context_mock.fetcher.tail.assert_called_with(context_mock.log_group_name,
                                                     filter_pattern=context_mock.filter_pattern,
                                                     start=context_mock.start_time)

        context_mock.formatter.do_format.assert_called_with(events_iterable)
        click_mock.echo.assert_has_calls([call(v, nl=False) for v in formatted_events])
