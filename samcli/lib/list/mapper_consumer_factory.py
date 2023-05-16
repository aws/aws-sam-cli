"""
The factory for returning the appropriate mapper and consumer
"""
from samcli.commands.list.json_consumer import StringConsumerJsonOutput
from samcli.commands.list.table_consumer import StringConsumerTableOutput
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.lib.list.endpoints.endpoints_to_table_mapper import EndpointsToTableMapper
from samcli.lib.list.list_interfaces import Mapper, MapperConsumerFactoryInterface, ProducersEnum
from samcli.lib.list.mapper_consumer_container import MapperConsumerContainer
from samcli.lib.list.resources.resources_to_table_mapper import ResourcesToTableMapper
from samcli.lib.list.stack_outputs.stack_output_to_table_mapper import StackOutputToTableMapper


class MapperConsumerFactory(MapperConsumerFactoryInterface):
    """
    Factory class to create factory objects that map a given producer and output format to a mapper and a consumer
    """

    def create(self, producer: ProducersEnum, output: str) -> MapperConsumerContainer:
        """
        Creates a MapperConsumerContainer that contains the resulting mapper and consumer given
        the producer and output format

        Parameters
        ----------
        producer: ProducersEnum
            An enum representing the producers (stack-outputs, resources, or endpoints producer)
        output: str
            The output format, either json or table

        Returns
        -------
        container: MapperConsumerContainer
            A MapperConsumerContainer containing the resulting mapper and consumer to be used by the producer
        """
        if output == "json":
            data_to_json_mapper = DataToJsonMapper()
            json_consumer = StringConsumerJsonOutput()
            container = MapperConsumerContainer(data_to_json_mapper, json_consumer)
            return container
        table_mapper: Mapper
        table_consumer = StringConsumerTableOutput()
        if producer == ProducersEnum.STACK_OUTPUTS_PRODUCER:
            table_mapper = StackOutputToTableMapper()
        elif producer == ProducersEnum.RESOURCES_PRODUCER:
            table_mapper = ResourcesToTableMapper()
        elif producer == ProducersEnum.ENDPOINTS_PRODUCER:
            table_mapper = EndpointsToTableMapper()
        container = MapperConsumerContainer(table_mapper, table_consumer)
        return container
