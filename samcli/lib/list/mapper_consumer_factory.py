"""
The factory for returning the appropriate mapper and consumer
"""
from samcli.lib.list.mapper_consumer_factory_interface import MapperConsumerFactoryInterface
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.lib.list.json_consumer import JsonConsumer
from samcli.lib.list.mapper_consumer_container import MapperConsumerContainer


class MapperConsumerFactory(MapperConsumerFactoryInterface):
    def create(self, producer, output):
        # Will add conditions here to return different sorts of containers later on
        new_data_to_json_mapper = DataToJsonMapper()
        new_json_consumer = JsonConsumer()
        new_container = MapperConsumerContainer(mapper=new_data_to_json_mapper, consumer=new_json_consumer)
        return new_container
