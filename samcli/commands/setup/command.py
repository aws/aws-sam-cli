"""
CLI command for "setup", which sets up a SAM development environment
"""
import boto3
import click

from botocore.config import Config
from botocore.exceptions import ClientError

from samcli.cli.main import pass_context, common_options, aws_creds_options
from samcli.commands.exceptions import UserException
from samcli.lib.telemetry.metrics import track_command

SHORT_HELP = "Set up development environment for AWS SAM applications."

HELP_TEXT = """
Sets up a development environment for AWS SAM applications.

Currently this creates, if one does not exist, a managed S3 bucket for your account in your working AWS region.
"""

SAM_CLI_STACK_NAME = "aws-sam-cli-managed-stack"

MANAGED_STACK_DEFINITION = """
AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Managed Stack for AWS SAM CLI

Resources:
  SamCliSourceBucket:
    Type: AWS::S3::Bucket
    Properties:
      Tags:
        - Key: ManagedStackSource
          Value: AwsSamCli

Outputs:
  SourceBucket:
    Value: !Ref SamCliSourceBucket
"""


@click.command("setup", short_help=SHORT_HELP, help=HELP_TEXT, context_settings=dict(max_content_width=120))
@common_options
@aws_creds_options
@pass_context
@track_command
def cli(ctx):
    do_cli(ctx.region, ctx.profile)  # pragma: no cover


def do_cli(region, profile):
    session = boto3.Session(profile_name=profile if profile else None)
    cloudformation_client = session.client("cloudformation", config=Config(region_name=region if region else None))
    create_or_get_stack(cloudformation_client)


def create_or_get_stack(cloudformation_client):
    stack = None
    try:
        ds_resp = cloudformation_client.describe_stacks(StackName=SAM_CLI_STACK_NAME)
        stacks = ds_resp["Stacks"]
        stack = stacks[0]
        click.echo("Found managed SAM CLI stack.")
    except ClientError:
        click.echo("Managed SAM CLI stack not found, creating.")
        stack = _create_stack(cloudformation_client)  # exceptions are not captured from subcommands
    # Sanity check for non-none stack? Sanity check for tag?
    tags = stack["Tags"]
    try:
        sam_cli_tag = next(t for t in tags if t["Key"] == "ManagedStackSource")
        if not sam_cli_tag["Value"] == "AwsSamCli":
            msg = (
                "Stack "
                + SAM_CLI_STACK_NAME
                + " ManagedStackSource tag shows "
                + sam_cli_tag["Value"]
                + " which does not match the AWS SAM CLI generated tag value of AwsSamCli. Failing as the stack was likely not created by the AWS SAM CLI."
            )
            raise UserException(msg)
    except StopIteration:
        msg = (
            "Stack  "
            + SAM_CLI_STACK_NAME
            + " exists, but the ManagedStackSource tag is missing. Failing as the stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg)
    outputs = stack["Outputs"]
    try:
        bucket_name = next(o for o in outputs if o["OutputKey"] == "SourceBucket")["OutputValue"]
    except StopIteration:
        msg = (
            "Stack "
            + SAM_CLI_STACK_NAME
            + " exists, but is missing the managed source bucket key. Failing as this stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg)
    # This bucket name is what we would write to a config file
    msg = "Source Bucket: " + bucket_name
    click.echo(msg)


def _create_stack(cloudformation_client):
    change_set_name = "InitialCreation"
    change_set_resp = cloudformation_client.create_change_set(
        StackName=SAM_CLI_STACK_NAME,
        TemplateBody=MANAGED_STACK_DEFINITION,
        Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
        ChangeSetType="CREATE",
        ChangeSetName=change_set_name,  # this must be unique for the stack, but we only create so that's fine
    )
    stack_id = change_set_resp["StackId"]
    click.echo("Waiting for managed stack change set to create.")
    change_waiter = cloudformation_client.get_waiter("change_set_create_complete")
    change_waiter.wait(
        ChangeSetName=change_set_name, StackName=SAM_CLI_STACK_NAME, WaiterConfig={"Delay": 15, "MaxAttempts": 60}
    )
    cloudformation_client.execute_change_set(ChangeSetName=change_set_name, StackName=SAM_CLI_STACK_NAME)
    click.echo("Waiting for managed stack to be created.")
    stack_waiter = cloudformation_client.get_waiter("stack_create_complete")
    stack_waiter.wait(StackName=stack_id, WaiterConfig={"Delay": 15, "MaxAttempts": 60})
    click.echo("Managed SAM CLI stack creation complete!")
    ds_resp = cloudformation_client.describe_stacks(StackName=SAM_CLI_STACK_NAME)
    stacks = ds_resp["Stacks"]
    return stacks[0]
