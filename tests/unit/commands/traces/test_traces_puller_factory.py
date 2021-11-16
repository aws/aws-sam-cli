from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.commands.traces.traces_puller_factory import (
    generate_trace_puller,
    generate_unformatted_xray_event_consumer,
    generate_xray_event_console_consumer,
)


class TestGenerateTracePuller(TestCase):
    @parameterized.expand(
        [
            (False,),
            (True,),
        ]
    )
    @patch("samcli.commands.traces.traces_puller_factory.generate_xray_event_console_consumer")
    @patch("samcli.commands.traces.traces_puller_factory.generate_unformatted_xray_event_consumer")
    @patch("samcli.commands.traces.traces_puller_factory.XRayTracePuller")
    @patch("samcli.commands.traces.traces_puller_factory.XRayServiceGraphPuller")
    @patch("samcli.commands.traces.traces_puller_factory.ObservabilityCombinedPuller")
    def test_generate_trace_puller(
        self,
        unformatted,
        patched_combine_puller,
        patched_xray_service_graph_puller,
        patched_xray_trace_puller,
        patched_generate_unformatted_consumer,
        patched_generate_console_consumer,
    ):
        given_xray_client = Mock()
        given_xray_trace_puller = Mock()
        given_xray_service_graph_puller = Mock()
        given_combine_puller = Mock()
        patched_xray_trace_puller.return_value = given_xray_trace_puller
        patched_xray_service_graph_puller.return_value = given_xray_service_graph_puller
        patched_combine_puller.return_value = given_combine_puller

        given_console_consumer = Mock()
        patched_generate_console_consumer.return_value = given_console_consumer

        given_file_consumer = Mock()
        patched_generate_unformatted_consumer.return_value = given_file_consumer

        actual_puller = generate_trace_puller(given_xray_client, unformatted)
        self.assertEqual(given_combine_puller, actual_puller)

        if unformatted:
            patched_generate_unformatted_consumer.assert_called_with()
            patched_xray_trace_puller.assert_called_with(given_xray_client, given_file_consumer)
        else:
            patched_generate_console_consumer.assert_called_once()
            patched_xray_trace_puller.assert_called_with(given_xray_client, given_console_consumer)

    @patch("samcli.commands.traces.traces_puller_factory.ObservabilityEventConsumerDecorator")
    @patch("samcli.commands.traces.traces_puller_factory.XRayTraceJSONMapper")
    @patch("samcli.commands.traces.traces_puller_factory.XRayTraceConsoleConsumer")
    def test_generate_file_consumer(self, patched_consumer, patched_trace_json_mapper, patched_consumer_decorator):
        given_consumer = Mock()
        patched_consumer_decorator.return_value = given_consumer

        actual_consumer = generate_unformatted_xray_event_consumer()
        self.assertEqual(given_consumer, actual_consumer)

        patched_trace_json_mapper.assert_called_once()
        patched_consumer.assert_called_with()

    @patch("samcli.commands.traces.traces_puller_factory.ObservabilityEventConsumerDecorator")
    @patch("samcli.commands.traces.traces_puller_factory.XRayTraceConsoleMapper")
    @patch("samcli.commands.traces.traces_puller_factory.XRayTraceConsoleConsumer")
    def test_generate_console_consumer(
        self,
        patched_console_consumer,
        patched_console_mapper,
        patched_consumer_decorator,
    ):
        given_consumer = Mock()
        patched_consumer_decorator.return_value = given_consumer

        actual_consumer = generate_xray_event_console_consumer()
        self.assertEqual(given_consumer, actual_consumer)

        patched_console_mapper.assert_called_once()
        patched_console_consumer.assert_called_once()
