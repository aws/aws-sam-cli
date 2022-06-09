"""
Display the Outputs of a SAM stack
"""
import logging
import json
import boto3
import click
from botocore.exceptions import ClientError, BotoCoreError

from samcli.commands.exceptions import RegionError
from samcli.commands.list.exceptions import StackOutputsError, NoOutputsForStackError
from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config

LOG = logging.getLogger(__name__)


class StackOutputsContext:
    def __init__(self, stack_name: str, output: str, region: str, profile: str):
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
        Returns the stack information for the stack

        Returns
        -------
            A dictionary containing the stack's information
        """
        cfn_client = self.cloudformation_client
        return cfn_client.describe_stacks(StackName=self.stack_name)

    def stack_exists(self, stack_name: str) -> bool:
        """
        Returns whether a stack exists in the region and is valid, and raises exceptions accordingly

        Parameters
        ----------
        stack_name: str
            Name of the stack that is deployed to CFN

        Returns
        -------
            A boolean value of whether the stack exists in the region
        """
        try:
            response = self.get_stack_info()
            if not response["Stacks"]:
                return False
            if "Outputs" not in response["Stacks"][0]:
                raise NoOutputsForStackError(stack_name=self.stack_name, msg=self.region)
            return True

        except ClientError as e:
            if "Stack with id {0} does not exist".format(stack_name) in str(e):
                LOG.debug("Stack with id %s does not exist", stack_name)
                return False
            LOG.error("ClientError Exception : %s", str(e))
            raise StackOutputsError(stack_name=self.stack_name, msg=str(e)) from e
        except BotoCoreError as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Botocore Exception : %s", str(e))
            raise StackOutputsError(stack_name=self.stack_name, msg=str(e)) from e

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
                raise RegionError(message="no region specified/found")

        client_provider = get_boto_client_provider_with_config(region=self.region, profile=self.profile)
        self.cloudformation_client = client_provider("cloudformation")

    def run(self) -> None:
        """
        Get the stack outputs for a stack
        """
        exists = self.stack_exists(self.stack_name)
        if exists:
            response = self.get_stack_info()
            click.echo(json.dumps(response["Stacks"][0]["Outputs"], indent=2))
        else:
            LOG.debug("Input stack does not exists on Cloudformation")
            click.echo(
                f"Error: The input stack {self.stack_name} does"
                f" not exist on Cloudformation in the region {self.region}"
            )
