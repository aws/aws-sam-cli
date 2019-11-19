"""
Bootstrap's user's development environment by creating cloud resources required by SAM CLI
"""

import json
import logging
import boto3

from botocore.config import Config
from botocore.exceptions import ClientError

from samcli import __version__
from samcli.cli.global_config import GlobalConfig
from samcli.commands.exceptions import UserException


LOG = logging.getLogger(__name__)
SAM_CLI_STACK_NAME = "aws-sam-cli-managed-stack"


def manage_stack(profile, region):
    session = boto3.Session(profile_name=profile if profile else None)
    cloudformation_client = session.client("cloudformation", config=Config(region_name=region if region else None))

    return _create_or_get_stack(cloudformation_client)


def _create_or_get_stack(cloudformation_client):
    stack = None
    try:
        ds_resp = cloudformation_client.describe_stacks(StackName=SAM_CLI_STACK_NAME)
        stacks = ds_resp["Stacks"]
        stack = stacks[0]
        LOG.info("\tFound managed SAM CLI stack.")
    except ClientError:
        LOG.info("\tManaged SAM CLI stack not found, creating.")
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
                + " which does not match the AWS SAM CLI generated tag value of AwsSamCli. "
                "Failing as the stack was likely not created by the AWS SAM CLI."
            )
            raise UserException(msg)
    except StopIteration:
        msg = (
            "Stack  " + SAM_CLI_STACK_NAME + " exists, but the ManagedStackSource tag is missing. "
            "Failing as the stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg)
    outputs = stack["Outputs"]
    try:
        bucket_name = next(o for o in outputs if o["OutputKey"] == "SourceBucket")["OutputValue"]
    except StopIteration:
        msg = (
            "Stack " + SAM_CLI_STACK_NAME + " exists, but is missing the managed source bucket key. "
            "Failing as this stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg)
    # This bucket name is what we would write to a config file
    return bucket_name


def _create_stack(cloudformation_client):
    change_set_name = "InitialCreation"
    change_set_resp = cloudformation_client.create_change_set(
        StackName=SAM_CLI_STACK_NAME,
        TemplateBody=_get_stack_template(),
        Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
        ChangeSetType="CREATE",
        ChangeSetName=change_set_name,  # this must be unique for the stack, but we only create so that's fine
    )
    stack_id = change_set_resp["StackId"]
    LOG.info("\tWaiting for managed stack change set to create.")
    change_waiter = cloudformation_client.get_waiter("change_set_create_complete")
    change_waiter.wait(
        ChangeSetName=change_set_name, StackName=SAM_CLI_STACK_NAME, WaiterConfig={"Delay": 15, "MaxAttempts": 60}
    )
    cloudformation_client.execute_change_set(ChangeSetName=change_set_name, StackName=SAM_CLI_STACK_NAME)
    LOG.info("\tWaiting for managed stack to be created.")
    stack_waiter = cloudformation_client.get_waiter("stack_create_complete")
    stack_waiter.wait(StackName=stack_id, WaiterConfig={"Delay": 15, "MaxAttempts": 60})
    LOG.info("\tManaged SAM CLI stack creation complete.")
    ds_resp = cloudformation_client.describe_stacks(StackName=SAM_CLI_STACK_NAME)
    stacks = ds_resp["Stacks"]
    return stacks[0]


def _get_stack_template():
    gc = GlobalConfig()
    info = {"version": __version__, "installationId": gc.installation_id}

    template = """
    AWSTemplateFormatVersion : '2010-09-09'
    Transform: AWS::Serverless-2016-10-31
    Description: Managed Stack for AWS SAM CLI

    Metadata:
        SamCliInfo: {info}

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

    return template.format(info=json.dumps(info))
