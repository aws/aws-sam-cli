"""
Display the Outputs of a SAM stack
"""

import logging
from typing import Optional

from samcli.commands.list.cli_common.list_common_context import ListContext
from samcli.lib.list.list_interfaces import ProducersEnum
from samcli.lib.list.mapper_consumer_factory import MapperConsumerFactory
from samcli.lib.list.stack_outputs.stack_outputs_producer import StackOutputsProducer

LOG = logging.getLogger(__name__)


class StackOutputsContext(ListContext):
    def __init__(self, stack_name: str, output: str, region: Optional[str], profile: Optional[str]):
        super().__init__()
        self.stack_name = stack_name
        self.output = output
        self.region = region
        self.profile = profile
        self.cloudformation_client = None

    def __enter__(self):
        self.init_clients()
        return self

    def __exit__(self, *args):
        pass

    def run(self) -> None:
        """
        Get the stack outputs for a stack
        """
        factory = MapperConsumerFactory()
        container = factory.create(producer=ProducersEnum.STACK_OUTPUTS_PRODUCER, output=self.output)

        producer = StackOutputsProducer(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            cloudformation_client=self.cloudformation_client,
            mapper=container.mapper,
            consumer=container.consumer,
        )
        producer.produce()
