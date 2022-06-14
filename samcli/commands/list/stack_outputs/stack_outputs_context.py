"""
Display the Outputs of a SAM stack
"""
import logging
import json
from typing import Optional
import boto3
import click
from botocore.exceptions import ClientError, BotoCoreError

from samcli.commands.exceptions import RegionError
from samcli.commands.list.exceptions import StackOutputsError, NoOutputsForStackError, StackDoesNotExistInRegionError
from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config


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

    def get_stack_info(self):
        """
        Returns the stack information for the stack passed in from the command line

        Returns
        -------
            A dictionary containing the stack's information
        """
        cfn_client = self.cloudformation_client
        return cfn_client.describe_stacks(StackName=self.stack_name)

    def stack_exists(self):
        """
        Returns the stack output information for the stack and raises exceptions accordingly

        Returns
        -------
            A dictionary containing the stack's information
        """

        try:
            response = self.get_stack_info()
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

    def run(self) -> None:
        """
        Get the stack outputs for a stack
        """

        response = self.stack_exists()
        click.echo(json.dumps(response["Stacks"][0]["Outputs"], indent=2))
