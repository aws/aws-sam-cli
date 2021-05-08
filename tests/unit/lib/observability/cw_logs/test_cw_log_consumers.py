from unittest import TestCase
from unittest.mock import patch, Mock, call

from samcli.lib.observability.cw_logs.cw_log_consumers import CWTerminalEventConsumer


class TestCWTerminalEventConsumer(TestCase):
    def setUp(self):
        self.consumer = CWTerminalEventConsumer()

    @patch("samcli.lib.observability.cw_logs.cw_log_consumers.click")
    def test_consume_with_event(self, patched_click):
        event = Mock()
        self.consumer.consume(event)
        patched_click.echo.assert_called_with(event, nl=False)
