from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.logs.console_consumers import CWConsoleEventConsumer


class TestCWConsoleEventConsumer(TestCase):
    def setUp(self):
        self.consumer = CWConsoleEventConsumer()

    @patch("samcli.commands.logs.console_consumers.click")
    def test_consume_with_event(self, patched_click):
        event = Mock()
        self.consumer.consume(event)
        patched_click.echo.assert_called_with(event.message, nl=False)
