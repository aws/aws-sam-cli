"""
Display the Outputs of a SAM stack
"""
import logging
from typing import Optional
import boto3
from samcli.lib.list.stack_outputs.stack_outputs_producer import StackOutputsProducer
from samcli.commands.exceptions import RegionError
from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config
from samcli.lib.list.mapper_consumer_factory import MapperConsumerFactory
from samcli.lib.list.list_interfaces import ProducersEnum

LOG = logging.getLogger(__name__)


class StackOutputsContext:
    def __init__(self, stack_name: str, output: str, region: Optional[str], profile: Optional[str]):
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

    def init_clients(self) -> None:
        """
        Initialize the clients being used by sam list.
        """
        if not self.region:
            session = boto3.Session()
            region = session.region_name
            if region:
                self.region = region
            else:
                raise RegionError(
                    message="No region was specified/found. "
                    "Please provide a region via the --region parameter or by the AWS_REGION environment variable."
                )

        client_provider = get_boto_client_provider_with_config(region=self.region, profile=self.profile)
        self.cloudformation_client = client_provider("cloudformation")

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
