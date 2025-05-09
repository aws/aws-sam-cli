"""
Bootstrap's user's development environment by creating cloud resources required by SAM CLI
"""

import json
import logging
from typing import Optional

import boto3
import click
from botocore.exceptions import ClientError

from samcli import __version__
from samcli.cli.global_config import GlobalConfig
from samcli.commands.exceptions import AWSServiceClientError, UserException
from samcli.lib.utils.managed_cloudformation_stack import StackOutput
from samcli.lib.utils.managed_cloudformation_stack import manage_stack as manage_cloudformation_stack

SAM_CLI_STACK_NAME = "aws-sam-cli-managed-default"
LOG = logging.getLogger(__name__)


def manage_stack(profile, region):
    outputs: StackOutput = manage_cloudformation_stack(
        profile=None, region=region, stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
    )

    bucket_name = outputs.get("SourceBucket")
    if bucket_name is None:
        msg = (
            "Stack " + SAM_CLI_STACK_NAME + " exists, but is missing the managed source bucket key. "
            "Failing as this stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg)
    # This bucket name is what we would write to a config file
    return bucket_name


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
