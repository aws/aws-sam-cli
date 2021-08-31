from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized, param

from samcli.lib.observability.observability_info_puller import ObservabilityEventConsumerDecorator


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
