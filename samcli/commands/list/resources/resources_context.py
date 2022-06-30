"""
Display the Resources of a SAM stack
"""
import logging
from typing import Optional
import boto3

from samcli.commands.exceptions import RegionError
from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config

from samcli.lib.list.resources.resource_mapping_producer import ResourceMappingProducer
from samcli.lib.list.mapper_consumer_factory import MapperConsumerFactory
from samcli.lib.list.list_interfaces import ProducersEnum


LOG = logging.getLogger(__name__)


class ResourcesContext:
    def __init__(
        self, stack_name: str, output: str, region: Optional[str], profile: Optional[str], template_file: Optional[str]
    ):
        self.stack_name = stack_name
        self.output = output
        self.region = region
        self.profile = profile
        self.template_file = template_file
        self.cloudformation_client = None
        self.iam_client = None

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
        self.iam_client = client_provider("iam")

    def run(self) -> None:
        """
        Get the resources for a stack
        """
        factory = MapperConsumerFactory()
        container = factory.create(producer=ProducersEnum.RESOURCES_PRODUCER, output=self.output)
        resource_producer = ResourceMappingProducer(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
            template_file=self.template_file,
            cloudformation_client=self.cloudformation_client,
            iam_client=self.iam_client,
            mapper=container.mapper,
            consumer=container.consumer,
        )
        resource_producer.produce()
