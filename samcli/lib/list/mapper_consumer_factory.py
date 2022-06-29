"""
The factory for returning the appropriate mapper and consumer
"""
from samcli.lib.list.list_interfaces import MapperConsumerFactoryInterface
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.commands.list.json_consumer import StringConsumerJsonOutput
from samcli.lib.list.mapper_consumer_container import MapperConsumerContainer
from samcli.lib.list.list_interfaces import ProducersEnum


class MapperConsumerFactory(MapperConsumerFactoryInterface):
    def create(self, producer: ProducersEnum, output: str) -> MapperConsumerContainer:
        # Will add conditions here to return different sorts of containers later on
        data_to_json_mapper = DataToJsonMapper()
        json_consumer = StringConsumerJsonOutput()
        container = MapperConsumerContainer(data_to_json_mapper, json_consumer)
        return container
