"""
The producer for the 'sam list stack-outputs' command
"""
import dataclasses
import logging
from typing import Any, Optional

from botocore.exceptions import BotoCoreError, ClientError

from samcli.commands.list.exceptions import (
    NoOutputsForStackError,
    SamListUnknownBotoCoreError,
    SamListUnknownClientError,
    StackDoesNotExistInRegionError,
)
from samcli.lib.list.list_interfaces import Producer
from samcli.lib.list.stack_outputs.stack_outputs import StackOutputs
from samcli.lib.utils.boto_utils import get_client_error_code

LOG = logging.getLogger(__name__)


class StackOutputsProducer(Producer):
    def __init__(self, stack_name, output, region, cloudformation_client, mapper, consumer):
        self.stack_name = stack_name
        self.output = output
        self.region = region
        self.cloudformation_client = cloudformation_client
        self.mapper = mapper
        self.consumer = consumer

    def get_stack_info(self) -> Optional[Any]:
        """
        Returns the stack output information for the stack and raises exceptions accordingly

        Returns
        -------
            A dictionary containing the stack's information
        """

        try:
            response = self.cloudformation_client.describe_stacks(StackName=self.stack_name)
            if not response.get("Stacks", []):
                raise StackDoesNotExistInRegionError(stack_name=self.stack_name, region=self.region)
            if len(response.get("Stacks", [])) > 0 and "Outputs" not in response.get("Stacks", [])[0]:
                raise NoOutputsForStackError(stack_name=self.stack_name, region=self.region)
            return response["Stacks"][0]["Outputs"]

        except ClientError as e:
            if get_client_error_code(e) == "ValidationError":
                LOG.debug("Stack with id %s does not exist", self.stack_name)
                raise StackDoesNotExistInRegionError(stack_name=self.stack_name, region=self.region) from e
            LOG.error("ClientError Exception : %s", str(e))
            raise SamListUnknownClientError(msg=str(e)) from e
        except BotoCoreError as e:
            LOG.error("Botocore Exception : %s", str(e))
            raise SamListUnknownBotoCoreError(msg=str(e)) from e

    def produce(self):
        response = self.get_stack_info()
        output_list = []
        for stack_output in response:
            stack_output_data = StackOutputs(
                OutputKey=stack_output.get("OutputKey", ""),
                OutputValue=stack_output.get("OutputValue", ""),
                Description=stack_output.get("Description", ""),
            )
            output_list.append(dataclasses.asdict(stack_output_data))
        mapped_output = self.mapper.map(output_list)
        self.consumer.consume(data=mapped_output)
