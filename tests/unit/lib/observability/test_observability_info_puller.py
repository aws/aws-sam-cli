from unittest import TestCase
from unittest.mock import Mock, patch, call

from parameterized import parameterized, param

from samcli.lib.observability.observability_info_puller import (
    ObservabilityEventConsumerDecorator,
    ObservabilityCombinedPuller,
)


class TestObservabilityEventConsumerDecorator(TestCase):
    def test_decorator(self):
        actual_consumer = Mock()
        event = Mock()

        consumer_decorator = ObservabilityEventConsumerDecorator([], actual_consumer)
        consumer_decorator.consume(event)

        actual_consumer.consume.assert_called_with(event)

    def test_decorator_with_mapper(self):
        actual_consumer = Mock()
        event = Mock()
        mapped_event = Mock()
        mapper = Mock()
        mapper.map.return_value = mapped_event

        consumer_decorator = ObservabilityEventConsumerDecorator([mapper], actual_consumer)
        consumer_decorator.consume(event)

        mapper.map.assert_called_with(event)
        actual_consumer.consume.assert_called_with(mapped_event)

    @parameterized.expand(
        [
            param([Mock()]),
            param([Mock(), Mock()]),
            param([Mock(), Mock(), Mock()]),
        ]
    )
    def test_decorator_with_mappers(self, mappers):
        actual_consumer = Mock()
        event = Mock()
        for mapper in mappers:
            mapper.map.return_value = event

        consumer_decorator = ObservabilityEventConsumerDecorator(mappers, actual_consumer)
        consumer_decorator.consume(event)

        actual_consumer.consume.assert_called_with(event)
        for mapper in mappers:
            mapper.map.assert_called_with(event)


class TestObservabilityCombinedPuller(TestCase):
    @patch("samcli.lib.observability.observability_info_puller.AsyncContext")
    def test_tail(self, patched_async_context):
        mocked_async_context = Mock()
        patched_async_context.return_value = mocked_async_context

        mock_puller_1 = Mock()
        mock_puller_2 = Mock()

        combined_puller = ObservabilityCombinedPuller([mock_puller_1, mock_puller_2])

        given_start_time = Mock()
        given_filter_pattern = Mock()
        combined_puller.tail(given_start_time, given_filter_pattern)

        patched_async_context.assert_called_once()
        mocked_async_context.assert_has_calls(
            [
                call.add_async_task(mock_puller_1.tail, given_start_time, given_filter_pattern),
                call.add_async_task(mock_puller_2.tail, given_start_time, given_filter_pattern),
                call.run_async(),
            ]
        )

    @patch("samcli.lib.observability.observability_info_puller.AsyncContext")
    def test_tail_cancel(self, patched_async_context):
        mocked_async_context = Mock()
        mocked_async_context.run_async.side_effect = KeyboardInterrupt()
        patched_async_context.return_value = mocked_async_context

        mock_puller_1 = Mock()
        mock_puller_2 = Mock()
        mock_puller_3 = Mock()

        child_combined_puller = ObservabilityCombinedPuller([mock_puller_3])

        combined_puller = ObservabilityCombinedPuller([mock_puller_1, mock_puller_2, child_combined_puller])

        given_start_time = Mock()
        given_filter_pattern = Mock()
        combined_puller.tail(given_start_time, given_filter_pattern)

        patched_async_context.assert_called_once()
        mocked_async_context.assert_has_calls(
            [
                call.add_async_task(mock_puller_1.tail, given_start_time, given_filter_pattern),
                call.add_async_task(mock_puller_2.tail, given_start_time, given_filter_pattern),
                call.add_async_task(child_combined_puller.tail, given_start_time, given_filter_pattern),
                call.run_async(),
            ]
        )

        self.assertTrue(mock_puller_1.stop_tailing.called)
        self.assertTrue(mock_puller_2.stop_tailing.called)
        self.assertTrue(mock_puller_3.stop_tailing.called)

    @patch("samcli.lib.observability.observability_info_puller.AsyncContext")
    def test_load_time_period(self, patched_async_context):
        mocked_async_context = Mock()
        patched_async_context.return_value = mocked_async_context

        mock_puller_1 = Mock()
        mock_puller_2 = Mock()

        combined_puller = ObservabilityCombinedPuller([mock_puller_1, mock_puller_2])

        given_start_time = Mock()
        given_end_time = Mock()
        given_filter_pattern = Mock()
        combined_puller.load_time_period(given_start_time, given_end_time, given_filter_pattern)

        patched_async_context.assert_called_once()
        mocked_async_context.assert_has_calls(
            [
                call.add_async_task(
                    mock_puller_1.load_time_period, given_start_time, given_end_time, given_filter_pattern
                ),
                call.add_async_task(
                    mock_puller_2.load_time_period, given_start_time, given_end_time, given_filter_pattern
                ),
                call.run_async(),
            ]
        )

    @patch("samcli.lib.observability.observability_info_puller.AsyncContext")
    def test_load_events(self, patched_async_context):
        mocked_async_context = Mock()
        patched_async_context.return_value = mocked_async_context

        mock_puller_1 = Mock()
        mock_puller_2 = Mock()

        combined_puller = ObservabilityCombinedPuller([mock_puller_1, mock_puller_2])

        given_event_ids = [Mock(), Mock()]
        combined_puller.load_events(given_event_ids)

        patched_async_context.assert_called_once()
        mocked_async_context.assert_has_calls(
            [
                call.add_async_task(mock_puller_1.load_events, given_event_ids),
                call.add_async_task(mock_puller_2.load_events, given_event_ids),
                call.run_async(),
            ]
        )
