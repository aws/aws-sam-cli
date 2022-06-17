"""
The producer for the 'sam list stack-outputs' command
"""
import dataclasses
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from samcli.commands.exceptions import RegionError
from samcli.commands.list.exceptions import StackOutputsError, NoOutputsForStackError, StackDoesNotExistInRegionError

from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config
from samcli.lib.list.producer import Producer
from samcli.lib.list.stack_outputs.stack_outputs import StackOutputs
from samcli.lib.list.mapper_consumer_factory import MapperConsumerFactory

LOG = logging.getLogger(__name__)


class StackOutputsProducer(Producer):
    def __init__(self, stack_name, output, region, profile):
        self.stack_name = stack_name
        self.output = output
        self.region = region
        self.profile = profile
        self.cloudformation_client = None
        self.mapper = None
        self.consumer = None
        self.factory = None

    def __enter__(self):
        self.init_clients()
        self.factory = MapperConsumerFactory()
        return self

    def __exit__(self, *args):
        pass

    def get_stack_info(self):
        """
        Returns the stack output information for the stack and raises exceptions accordingly

        Returns
        -------
            A dictionary containing the stack's information
        """

        try:
            response = self.cloudformation_client.describe_stacks(StackName=self.stack_name)
            if not response["Stacks"]:
                raise StackDoesNotExistInRegionError(stack_name=self.stack_name, region=self.region)
            if "Outputs" not in response["Stacks"][0]:
                raise NoOutputsForStackError(stack_name=self.stack_name, region=self.region)
            return response

        except ClientError as e:
            if "Stack with id {0} does not exist".format(self.stack_name) in str(e):
                LOG.debug("Stack with id %s does not exist", self.stack_name)
                raise StackDoesNotExistInRegionError(stack_name=self.stack_name, region=self.region) from e
            LOG.error("ClientError Exception : %s", str(e))
            raise StackOutputsError(msg=str(e)) from e
        except BotoCoreError as e:
            LOG.error("Botocore Exception : %s", str(e))
            raise StackOutputsError(msg=str(e)) from e

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

    def produce(self):
        new_container = self.factory.create(producer="stackoutputsproducer", output=self.output)
        self.mapper = new_container.mapper
        self.consumer = new_container.consumer
        response = self.get_stack_info()
        for stack_output in response["Stacks"][0]["Outputs"]:
            stack_output_data = StackOutputs(
                OutputKey=stack_output["OutputKey"],
                OutputValue=stack_output["OutputValue"],
                Description=stack_output["Description"],
            )
            mapped_output = self.mapper.map(dataclasses.asdict(stack_output_data))
            self.consumer.consume(mapped_output)
