"""
Bootstrap's user's development environment by creating cloud resources required by SAM CLI
"""

import json
import logging

import boto3

import click

from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError, NoRegionError, NoCredentialsError

from samcli.commands.bootstrap.exceptions import ManagedStackError
from samcli import __version__
from samcli.cli.global_config import GlobalConfig
from samcli.commands.exceptions import UserException, CredentialsError, RegionError


SAM_CLI_STACK_NAME = "aws-sam-cli-managed-default"
LOG = logging.getLogger(__name__)


def manage_stack(profile, region):
    try:
        cloudformation_client = boto3.client("cloudformation", config=Config(region_name=region if region else None))
    except NoCredentialsError as ex:
        raise CredentialsError(
            "Error Setting Up Managed Stack Client: Unable to resolve credentials for the AWS SDK for Python client. Please see their documentation for options to pass in credentials: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html"
        ) from ex
    except NoRegionError as ex:
        raise RegionError(
            "Error Setting Up Managed Stack Client: Unable to resolve a region. Please provide a region via the --region parameter or by the AWS_REGION environment variable."
        ) from ex
    return _create_or_get_stack(cloudformation_client)


def _create_or_get_stack(cloudformation_client):
    try:
        stack = None
        try:
            ds_resp = cloudformation_client.describe_stacks(StackName=SAM_CLI_STACK_NAME)
            stacks = ds_resp["Stacks"]
            stack = stacks[0]
            click.echo("\n\tLooking for resources needed for deployment: Found!")
        except ClientError:
            click.echo("\n\tLooking for resources needed for deployment: Not found.")
            stack = _create_stack(cloudformation_client)  # exceptions are not captured from subcommands

        _check_sanity_of_stack(stack)

        outputs = stack["Outputs"]
        try:
            bucket_name = next(o for o in outputs if o["OutputKey"] == "SourceBucket")["OutputValue"]
        except StopIteration as ex:
            msg = (
                "Stack " + SAM_CLI_STACK_NAME + " exists, but is missing the managed source bucket key. "
                "Failing as this stack was likely not created by the AWS SAM CLI."
            )
            raise UserException(msg) from ex
        # This bucket name is what we would write to a config file
        return bucket_name
    except (ClientError, BotoCoreError) as ex:
        LOG.debug("Failed to create managed resources", exc_info=ex)
        raise ManagedStackError(str(ex)) from ex


def _check_sanity_of_stack(stack):
    tags = stack.get("Tags", None)
    outputs = stack.get("Outputs", None)

    # For some edge cases, stack could be in invalid state
    # Check if stack information contains the Tags and Outputs as we expected
    if tags is None or outputs is None:
        stack_state = stack.get("StackName", None)
        msg = (
            f"Stack {SAM_CLI_STACK_NAME} is missing Tags and/or Outputs information and therefore not in a "
            f"healthy state (Current state:{stack_state}). Failing as the stack was likely not created "
            f"by the AWS SAM CLI"
        )
        raise UserException(msg)

    # Sanity check for non-none stack? Sanity check for tag?
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
    except StopIteration as ex:
        msg = (
            "Stack  " + SAM_CLI_STACK_NAME + " exists, but the ManagedStackSource tag is missing. "
            "Failing as the stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg) from ex


def _create_stack(cloudformation_client):
    click.echo("\tCreating the required resources...")
    change_set_name = "InitialCreation"
    change_set_resp = cloudformation_client.create_change_set(
        StackName=SAM_CLI_STACK_NAME,
        TemplateBody=_get_stack_template(),
        Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
        ChangeSetType="CREATE",
        ChangeSetName=change_set_name,  # this must be unique for the stack, but we only create so that's fine
    )
    stack_id = change_set_resp["StackId"]
    change_waiter = cloudformation_client.get_waiter("change_set_create_complete")
    change_waiter.wait(
        ChangeSetName=change_set_name, StackName=SAM_CLI_STACK_NAME, WaiterConfig={"Delay": 15, "MaxAttempts": 60}
    )
    cloudformation_client.execute_change_set(ChangeSetName=change_set_name, StackName=SAM_CLI_STACK_NAME)
    stack_waiter = cloudformation_client.get_waiter("stack_create_complete")
    stack_waiter.wait(StackName=stack_id, WaiterConfig={"Delay": 15, "MaxAttempts": 60})
    ds_resp = cloudformation_client.describe_stacks(StackName=SAM_CLI_STACK_NAME)
    stacks = ds_resp["Stacks"]
    click.echo("\tSuccessfully created!")
    return stacks[0]


def _get_stack_template():
    gc = GlobalConfig()
    info = {"version": __version__, "installationId": gc.installation_id if gc.installation_id else "unknown"}

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
          VersioningConfiguration:
            Status: Enabled
          Tags:
            - Key: ManagedStackSource
              Value: AwsSamCli

      SamCliSourceBucketBucketPolicy:
        Type: AWS::S3::BucketPolicy
        Properties:
          Bucket: !Ref SamCliSourceBucket
          PolicyDocument:
            Statement:
              -
                Action:
                  - "s3:GetObject"
                Effect: "Allow"
                Resource:
                  Fn::Join:
                    - ""
                    -
                      - "arn:"
                      - !Ref AWS::Partition
                      - ":s3:::"
                      - !Ref SamCliSourceBucket
                      - "/*"
                Principal:
                  Service: serverlessrepo.amazonaws.com

    Outputs:
      SourceBucket:
        Value: !Ref SamCliSourceBucket
    """

    return template.format(info=json.dumps(info))
