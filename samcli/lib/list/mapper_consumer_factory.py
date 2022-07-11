"""
The factory for returning the appropriate mapper and consumer
"""
from samcli.lib.list.list_interfaces import MapperConsumerFactoryInterface
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.commands.list.json_consumer import StringConsumerJsonOutput
from samcli.commands.list.table_consumer import StringConsumerTableOutput
from samcli.lib.list.mapper_consumer_container import MapperConsumerContainer
from samcli.lib.list.list_interfaces import ProducersEnum
from samcli.lib.list.stack_outputs.stack_output_to_table_mapper import StackOutputToTableMapper


class MapperConsumerFactory(MapperConsumerFactoryInterface):
    def create(self, producer: ProducersEnum, output: str) -> MapperConsumerContainer:
        # Will add conditions here to return different sorts of containers later on
        if output == "json":
            data_to_json_mapper = DataToJsonMapper()
            json_consumer = StringConsumerJsonOutput()
            container = MapperConsumerContainer(data_to_json_mapper, json_consumer)
            return container
        stack_outputs_mapper = StackOutputToTableMapper()
        table_consumer = StringConsumerTableOutput()
        container = MapperConsumerContainer(stack_outputs_mapper, table_consumer)
        return container
