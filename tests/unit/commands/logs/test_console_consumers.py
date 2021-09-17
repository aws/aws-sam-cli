from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.commands.logs.console_consumers import CWConsoleEventConsumer


class TestCWConsoleEventConsumer(TestCase):
    @parameterized.expand(
        [
            (True,),
            (False,),
        ]
    )
    @patch("samcli.commands.logs.console_consumers.click")
    def test_consumer_with_event(self, add_newline, patched_click):
        consumer = CWConsoleEventConsumer(add_newline)
        event = Mock()
        consumer.consume(event)

        expected_new_line_param = add_newline if add_newline is not None else True
        patched_click.echo.assert_called_with(event.message, nl=expected_new_line_param)

    @patch("samcli.commands.logs.console_consumers.click")
    def test_default_consumer_with_event(self, patched_click):
        consumer = CWConsoleEventConsumer()
        event = Mock()
        consumer.consume(event)

        patched_click.echo.assert_called_with(event.message, nl=False)
