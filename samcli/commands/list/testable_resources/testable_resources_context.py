"""
Display of the Testable Resources of a SAM stack
"""
import logging
from typing import Optional

from samcli.commands.list.cli_common.list_common_context import ListContext
from samcli.lib.list.testable_resources.testable_resources_producer import TestableResourcesProducer
from samcli.lib.list.mapper_consumer_factory import MapperConsumerFactory
from samcli.lib.list.list_interfaces import ProducersEnum

LOG = logging.getLogger(__name__)


class TestableResourcesContext(ListContext):
    def __init__(
        self, stack_name: str, output: str, region: Optional[str], profile: Optional[str], template_file: Optional[str]
    ):
        super().__init__()
        self.stack_name = stack_name
        self.output = output
        self.region = region
        self.profile = profile
        self.template_file = template_file
        self.iam_client = None
        self.cloudcontrol_client = None
        self.apigateway_client = None
        self.apigatewayv2_client = None

    def __enter__(self):
        self.init_clients()
        return self

    def __exit__(self, *args):
        pass

    def init_clients(self) -> None:
        """
        Initialize the clients being used by sam list.
        """
        super().init_clients()
        self.iam_client = self.client_provider("iam")
        self.cloudcontrol_client = self.client_provider("cloudcontrol")
        self.apigateway_client = self.client_provider("apigateway")
        self.apigatewayv2_client = self.client_provider("apigatewayv2")

    def run(self) -> None:
        """
        Get the resources for a stack
        """
        factory = MapperConsumerFactory()
        container = factory.create(producer=ProducersEnum.TESTABLE_RESOURCES_PRODUCER, output=self.output)
        testable_resource_producer = TestableResourcesProducer(
            stack_name=self.stack_name,
            region=self.region,
            profile=self.profile,
            template_file=self.template_file,
            cloudformation_client=self.cloudformation_client,
            iam_client=self.iam_client,
            cloudcontrol_client=self.cloudcontrol_client,
            apigateway_client=self.apigateway_client,
            apigatewayv2_client=self.apigatewayv2_client,
            mapper=container.mapper,
            consumer=container.consumer,
        )
        testable_resource_producer.produce()
