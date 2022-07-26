"""
The factory for returning the appropriate mapper and consumer
"""
from samcli.lib.list.list_interfaces import MapperConsumerFactoryInterface
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.commands.list.json_consumer import StringConsumerJsonOutput
from samcli.commands.list.table_consumer import StringConsumerTableOutput
from samcli.lib.list.mapper_consumer_container import MapperConsumerContainer
from samcli.lib.list.stack_outputs.stack_output_to_table_mapper import StackOutputToTableMapper
from samcli.lib.list.resources.resources_to_table_mapper import ResourcesToTableMapper
from samcli.lib.list.testable_resources.testable_resources_to_table_mapper import TestableResourcesToTableMapper
from samcli.lib.list.list_interfaces import ProducersEnum, Mapper


class MapperConsumerFactory(MapperConsumerFactoryInterface):
    def create(self, producer: ProducersEnum, output: str) -> MapperConsumerContainer:
        # Will add conditions here to return different sorts of containers later on
        if output == "json":
            data_to_json_mapper = DataToJsonMapper()
            json_consumer = StringConsumerJsonOutput()
            container = MapperConsumerContainer(data_to_json_mapper, json_consumer)
            return container
        table_mapper: Mapper
        table_consumer = StringConsumerTableOutput()
        if producer == ProducersEnum.STACK_OUTPUTS_PRODUCER:
            table_mapper = StackOutputToTableMapper()
        # add conditional for when adding in the testable resources table
        elif producer == ProducersEnum.RESOURCES_PRODUCER:
            table_mapper = ResourcesToTableMapper()
        else:
            table_mapper = TestableResourcesToTableMapper()
        container = MapperConsumerContainer(table_mapper, table_consumer)
        return container
