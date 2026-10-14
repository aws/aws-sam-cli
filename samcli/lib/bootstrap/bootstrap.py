"""
Bootstrap's user's development environment by creating cloud resources required by SAM CLI
"""

import json
import logging
from typing import Any, Dict, Optional

import boto3
import click
from botocore.exceptions import ClientError

from samcli import __version__
from samcli.cli.global_config import GlobalConfig
from samcli.commands.exceptions import AWSServiceClientError, UserException
from samcli.lib.utils.managed_cloudformation_stack import StackOutput
from samcli.lib.utils.managed_cloudformation_stack import manage_stack as manage_cloudformation_stack
from samcli.lib.utils.managed_cloudformation_stack import update_stack as update_cloudformation_stack
from samcli.lib.utils.resources import AWS_SERVERLESS_WEBFUNCTION

SAM_CLI_STACK_NAME = "aws-sam-cli-managed-default"
# Bucket policy statement that lets Lambda read Web Function code from the managed bucket
WEB_FUNCTION_CODE_ACCESS_SID = "AllowLambdaWebFunctionCodeAccess"
WEB_FUNCTION_REVISION_SOURCE_ARN = "arn:${AWS::Partition}:lambda:*:${AWS::AccountId}:web-function/*/revision/*"
LOG = logging.getLogger(__name__)


def manage_stack(profile, region, web_function_code_access: bool = False):
    """
    Get or create the managed stack and return its source bucket name.

    Parameters
    ----------
    profile
        AWS named profile
    region
        AWS Region
    web_function_code_access : bool
        Make sure the managed bucket policy lets Lambda read Web Function code, updating a managed stack created
        by an earlier SAM CLI version if needed
    """
    outputs: StackOutput = manage_cloudformation_stack(
        profile=None, region=region, stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
    )
    if web_function_code_access:
        _ensure_web_function_code_access(region)

    bucket_name = outputs.get("SourceBucket")
    if bucket_name is None:
        msg = (
            "Stack " + SAM_CLI_STACK_NAME + " exists, but is missing the managed source bucket key. "
            "Failing as this stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg)
    # This bucket name is what we would write to a config file
    return bucket_name


def template_has_web_functions(template_dict: Optional[Dict]) -> bool:
    """Return True if the template defines an AWS::Serverless::WebFunction resource."""
    resources = (template_dict or {}).get("Resources") or {}
    return any(
        isinstance(resource, dict) and resource.get("Type") == AWS_SERVERLESS_WEBFUNCTION
        for resource in resources.values()
    )


def stacks_need_web_function_code_access(stacks: Any) -> bool:
    """
    Return True if the stacks (including nested stacks) define an AWS::Serverless::WebFunction whose code is uploaded
    from a local path. Returns False if the stacks can't be inspected.
    """
    # Imported here to avoid a circular import
    from samcli.lib.package.web_function_code_access import (  # pylint: disable=import-outside-toplevel
        stacks_have_web_functions,
    )

    try:
        return stacks_have_web_functions(stacks, local_code_only=True)
    except Exception:  # pylint: disable=broad-except
        LOG.debug("Could not inspect stacks for Web Functions", exc_info=True)
        return False


def template_file_has_web_functions(template_file: Optional[str]) -> bool:
    """
    Return True if the template file, or a nested stack it references, defines an AWS::Serverless::WebFunction whose
    code is uploaded from a local path.
    """
    # Imported here to avoid a circular import
    # pylint: disable=import-outside-toplevel
    from samcli.lib.package.web_function_code_access import stacks_have_web_functions
    from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider

    if not template_file:
        return False
    try:
        stacks, _ = SamLocalStackProvider.get_stacks(template_file)
        return stacks_have_web_functions(stacks, local_code_only=True)
    except Exception:  # pylint: disable=broad-except
        # An unreadable template fails later with a clearer error
        LOG.debug("Could not load stacks from %s to look for Web Functions", template_file, exc_info=True)
        return False


def _ensure_web_function_code_access(region: Optional[str]) -> None:
    """
    Update the managed stack if its bucket policy doesn't let Lambda read Web Function code.

    Managed stacks created by earlier SAM CLI versions don't have the statement, and the managed stack is otherwise
    never updated after it's created.
    """
    cloudformation_client = boto3.client("cloudformation", region_name=region)
    try:
        template_body = cloudformation_client.get_template(StackName=SAM_CLI_STACK_NAME, TemplateStage="Original")[
            "TemplateBody"
        ]
    except ClientError as ex:
        raise AWSServiceClientError(f"Failed to read the template of managed stack {SAM_CLI_STACK_NAME}: {ex}") from ex
    # TemplateBody is a string for JSON templates and a dict for some clients; the Sid check works on either
    if WEB_FUNCTION_CODE_ACCESS_SID in str(template_body):
        return

    click.echo(
        f"\tUpdating managed stack {SAM_CLI_STACK_NAME} so that Lambda Web Functions can read code from the managed "
        "S3 bucket"
    )
    try:
        update_cloudformation_stack(
            profile=None, region=region, stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
        )
    except Exception as ex:
        raise UserException(
            f"Failed to update managed stack {SAM_CLI_STACK_NAME} so that Lambda Web Functions can read code from "
            f"its S3 bucket: {ex}\nUpdate the stack with permission to modify its bucket policy, or deploy with "
            "--s3-bucket set to a versioned bucket whose policy allows lambda.amazonaws.com to call s3:GetObject "
            "and s3:GetObjectVersion."
        ) from ex


def print_managed_s3_bucket_info(s3_bucket: str):
    """
    Print information about the managed S3 bucket.

    Parameters
    ----------
    s3_bucket : str
        The name of the managed S3 bucket
    """
    message = f"\n\tManaged S3 bucket: {s3_bucket}"
    click.secho(message, bold=True)
    click.echo("\tAuto resolution of buckets can be turned off by setting resolve_s3=False")
    click.echo("\tTo use a specific S3 bucket, set --s3-bucket=<bucket_name>")
    click.echo("\tAbove settings can be stored in samconfig.toml")


def get_current_account_id(profile: Optional[str] = None):
    """Returns account ID based on used AWS credentials."""
    session = boto3.Session(profile_name=profile)
    sts_client = session.client("sts")
    try:
        caller_identity = sts_client.get_caller_identity()
    except ClientError as ex:
        if ex.response["Error"]["Code"] == "InvalidClientTokenId":
            raise AWSServiceClientError("Cannot identify account due to invalid configured credentials.") from ex
        raise AWSServiceClientError("Cannot identify account based on configured credentials.") from ex
    if "Account" not in caller_identity:
        raise AWSServiceClientError("Cannot identify account based on configured credentials.")
    return caller_identity["Account"]


def _get_stack_template():
    gc = GlobalConfig()
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Transform": "AWS::Serverless-2016-10-31",
        "Description": "Managed Stack for AWS SAM CLI",
        "Metadata": {
            "SamCliInfo": {
                "version": __version__,
                "installationId": gc.installation_id if gc.installation_id else "unknown",
            }
        },
        "Resources": {
            "SamCliSourceBucket": {
                "Type": "AWS::S3::Bucket",
                "Properties": {
                    "PublicAccessBlockConfiguration": {
                        "BlockPublicPolicy": "true",
                        "BlockPublicAcls": "true",
                        "IgnorePublicAcls": "true",
                        "RestrictPublicBuckets": "true",
                    },
                    "BucketEncryption": {
                        "ServerSideEncryptionConfiguration": [
                            {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}
                        ]
                    },
                    "VersioningConfiguration": {"Status": "Enabled"},
                    "Tags": [{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
                },
            },
            "SamCliSourceBucketBucketPolicy": {
                "Type": "AWS::S3::BucketPolicy",
                "Properties": {
                    "Bucket": {"Ref": "SamCliSourceBucket"},
                    "PolicyDocument": {
                        "Statement": [
                            {
                                "Action": ["s3:GetObject"],
                                "Effect": "Allow",
                                "Resource": {
                                    "Fn::Join": [
                                        "",
                                        [
                                            "arn:",
                                            {"Ref": "AWS::Partition"},
                                            ":s3:::",
                                            {"Ref": "SamCliSourceBucket"},
                                            "/*",
                                        ],
                                    ]
                                },
                                "Principal": {"Service": "serverlessrepo.amazonaws.com"},
                                "Condition": {"StringEquals": {"aws:SourceAccount": {"Ref": "AWS::AccountId"}}},
                            },
                            {
                                "Sid": WEB_FUNCTION_CODE_ACCESS_SID,
                                "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                                "Effect": "Allow",
                                "Resource": {
                                    "Fn::Join": [
                                        "",
                                        [
                                            "arn:",
                                            {"Ref": "AWS::Partition"},
                                            ":s3:::",
                                            {"Ref": "SamCliSourceBucket"},
                                            "/*",
                                        ],
                                    ]
                                },
                                "Principal": {"Service": "lambda.amazonaws.com"},
                                "Condition": {
                                    "StringEquals": {"aws:SourceAccount": {"Ref": "AWS::AccountId"}},
                                    "ArnLike": {"aws:SourceArn": {"Fn::Sub": WEB_FUNCTION_REVISION_SOURCE_ARN}},
                                },
                            },
                            {
                                "Action": ["s3:*"],
                                "Effect": "Deny",
                                "Resource": [
                                    {
                                        "Fn::Join": [
                                            "",
                                            [
                                                "arn:",
                                                {"Ref": "AWS::Partition"},
                                                ":s3:::",
                                                {"Ref": "SamCliSourceBucket"},
                                            ],
                                        ]
                                    },
                                    {
                                        "Fn::Join": [
                                            "",
                                            [
                                                "arn:",
                                                {"Ref": "AWS::Partition"},
                                                ":s3:::",
                                                {"Ref": "SamCliSourceBucket"},
                                                "/*",
                                            ],
                                        ]
                                    },
                                ],
                                "Principal": "*",
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            },
                        ]
                    },
                },
            },
        },
        "Outputs": {"SourceBucket": {"Value": {"Ref": "SamCliSourceBucket"}}},
    }
    return json.dumps(template)
