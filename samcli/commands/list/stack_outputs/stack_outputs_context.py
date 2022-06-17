"""
Display the Outputs of a SAM stack
"""
import logging
from typing import Optional
from samcli.lib.list.stack_outputs.stack_outputs_producer import StackOutputsProducer

LOG = logging.getLogger(__name__)


class StackOutputsContext:
    def __init__(self, stack_name: str, output: str, region: Optional[str], profile: Optional[str]):
        self.stack_name = stack_name
        self.output = output
        self.region = region
        self.profile = profile
        self.cloudformation_client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self) -> None:
        """
        Get the stack outputs for a stack
        """
        with StackOutputsProducer(
            stack_name=self.stack_name, output=self.output, region=self.region, profile=self.profile
        ) as producer:
            producer.produce()
