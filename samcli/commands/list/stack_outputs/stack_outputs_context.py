"""
Display the Outputs of a SAM stack
"""
import logging
import json
import boto3
import click
from botocore.exceptions import ClientError, BotoCoreError

from samcli.lib.utils.boto_utils import get_boto_config_with_user_agent
from samcli.cli.context import Context
from samcli.commands.list.exceptions import NoRegionError


LOG = logging.getLogger(__name__)


class StackOutputsContext:
    def __init__(self, stack_name, output, region, profile):
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
        return self.cloudformation_client.describe_stacks(StackName=self.stack_name)

    def stack_exists(self, stack_name):
        input_stack_does_not_exist_in_region = (
            f"Error: The input stack {self.stack_name} does" f" not exist on Cloudformation in the region {self.region}"
        )
        outputs_do_not_exist_in_stack = (
            f"Error: Outputs do not exist for the input stack {self.stack_name}"
            f" on Cloudformation in the region {self.region}"
        )
        try:
            response = self.get_stack_info()
            if not response["Stacks"]:
                return False, input_stack_does_not_exist_in_region
            if "Outputs" not in response["Stacks"][0]:
                return False, outputs_do_not_exist_in_stack
            return True, None

        except ClientError as e:
            if "Stack with id {0} does not exist".format(stack_name) in str(e):
                LOG.debug("Stack with id %s does not exist", stack_name)
                return False, input_stack_does_not_exist_in_region
            LOG.error("ClientError Exception : %s", str(e))
            return False, "Error: " + str(e)
        except BotoCoreError as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Botocore Exception : %s", str(e))
            return False, "Error: " + str(e)

    def init_clients(self):
        """
        Initialize the clients being used by sam list.
        """
        if not self.region:
            session = boto3.Session()
            region = session.region_name
            if region:
                self.region = region
            else:
                raise NoRegionError(stack_name=self.stack_name, msg="no region specified/found")

        if self.profile:
            Context.get_current_context().profile = self.profile
        if self.region:
            Context.get_current_context().region = self.region

        boto_config = get_boto_config_with_user_agent()
        self.cloudformation_client = boto3.client(
            "cloudformation", region_name=self.region if self.region else None, config=boto_config
        )

    def run(self):
        exists = self.stack_exists(self.stack_name)
        if exists:
            if exists[0]:
                response = self.get_stack_info()
                click.echo(json.dumps(response["Stacks"][0]["Outputs"], indent=2))
            else:
                LOG.debug("Input stack does not exists on Cloudformation")
                click.echo(exists[1])
        else:
            click.echo(
                f"Error: The input stack {self.stack_name} does"
                f" not exist on Cloudformation in the region {self.region}"
            )
