from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.traces.trace_console_consumers import XRayTraceConsoleConsumer


class TestTraceConsoleConsumers(TestCase):
    @patch("samcli.commands.traces.trace_console_consumers.click")
    def test_console_consumer(self, patched_click):
        event = Mock()
        consumer = XRayTraceConsoleConsumer()
        consumer.consume(event)

        patched_click.echo.assert_called_with(event.message)
