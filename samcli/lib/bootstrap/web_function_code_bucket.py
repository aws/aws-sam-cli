"""
Per-stack S3 bucket for AWS::Serverless::WebFunction code.

Lambda Web Functions read their code from S3 for as long as a revision exists, so the code can't live in the shared
managed bucket, which users can empty or delete without affecting Event Functions. Each deployed stack that has a
Web Function with local code gets its own bucket, in a stack that SAM CLI creates the first time it's needed and
deletes after the deployed stack is deleted.
"""

import json
import logging
from typing import Any, Dict, Optional

import click
from botocore.exceptions import ClientError

from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.managed_cloudformation_stack import StackOutput, manage_stack

LOG = logging.getLogger(__name__)

CODE_BUCKET_OUTPUT_KEY = "WebFunctionCodeBucket"
# Revisions of any Web Function in this account. Lambda reads a revision's code on its behalf.
WEB_FUNCTION_REVISION_SOURCE_ARN = "arn:${AWS::Partition}:lambda:*:${AWS::AccountId}:web-function/*/revision/*"


class WebFunctionCodeBucketStack:
    """Names the code bucket stack of a deployed stack."""

    def __init__(self, parent_stack_name: str) -> None:
        self.parent_stack_name = parent_stack_name
        # 128 character stack name limit: 100 + 1 + 8 + 16
        self.stack_name = f"{parent_stack_name[:100]}-{str_checksum(parent_stack_name)[:8]}-WebFunctionCode"


def get_code_bucket_template(parent_stack_name: str) -> str:
    """Return the template of the code bucket stack."""
    bucket_arn = {"Fn::GetAtt": ["CodeBucket", "Arn"]}
    objects_arn = {"Fn::Sub": "${CodeBucket.Arn}/*"}
    template: Dict[str, Any] = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": f"AWS SAM CLI managed bucket for the Lambda Web Function code of stack {parent_stack_name}",
        "Resources": {
            "CodeBucket": {
                "Type": "AWS::S3::Bucket",
                "Properties": {
                    # Each revision pins one object version for as long as it exists
                    "VersioningConfiguration": {"Status": "Enabled"},
                    # Lambda can't read objects encrypted with the AWS managed key (aws/s3)
                    "BucketEncryption": {
                        "ServerSideEncryptionConfiguration": [
                            {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                        ]
                    },
                    "PublicAccessBlockConfiguration": {
                        "BlockPublicAcls": True,
                        "BlockPublicPolicy": True,
                        "IgnorePublicAcls": True,
                        "RestrictPublicBuckets": True,
                    },
                    "Tags": [
                        {"Key": "ManagedStackSource", "Value": "AwsSamCli"},
                        {"Key": "SamCliParentStack", "Value": parent_stack_name},
                    ],
                },
            },
            "CodeBucketPolicy": {
                "Type": "AWS::S3::BucketPolicy",
                "Properties": {
                    "Bucket": {"Ref": "CodeBucket"},
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "AllowLambdaWebFunctionCodeAccess",
                                "Effect": "Allow",
                                "Principal": {"Service": "lambda.amazonaws.com"},
                                "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                                "Resource": objects_arn,
                                "Condition": {
                                    "StringEquals": {"aws:SourceAccount": {"Ref": "AWS::AccountId"}},
                                    "ArnLike": {"aws:SourceArn": {"Fn::Sub": WEB_FUNCTION_REVISION_SOURCE_ARN}},
                                },
                            },
                            {
                                "Sid": "DenyInsecureTransport",
                                "Effect": "Deny",
                                "Principal": "*",
                                "Action": "s3:*",
                                "Resource": [bucket_arn, objects_arn],
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            },
                        ],
                    },
                },
            },
        },
        "Outputs": {CODE_BUCKET_OUTPUT_KEY: {"Value": {"Ref": "CodeBucket"}}},
    }
    return json.dumps(template)


def manage_web_function_code_bucket(parent_stack_name: str, region: Optional[str], profile: Optional[str]) -> str:
    """
    Get or create the code bucket stack of a deployed stack, and return the bucket name.
    """
    code_stack = WebFunctionCodeBucketStack(parent_stack_name)
    click.echo(f"\n\tLooking for the Lambda Web Function code bucket of stack {parent_stack_name}")
    outputs: StackOutput = manage_stack(
        region=region,
        stack_name=code_stack.stack_name,
        template_body=get_code_bucket_template(parent_stack_name),
        profile=profile,
    )
    bucket_name = outputs.get(CODE_BUCKET_OUTPUT_KEY)
    if not bucket_name:
        raise click.ClickException(
            f"Stack {code_stack.stack_name} exists but has no {CODE_BUCKET_OUTPUT_KEY} output. It was likely not "
            "created by the AWS SAM CLI."
        )
    click.echo(f"\tLambda Web Function code bucket: {bucket_name}")
    return bucket_name


def delete_web_function_code_bucket(parent_stack_name: str, cloudformation_client: Any, s3_client: Any) -> bool:
    """
    Empty and delete the code bucket stack of a deployed stack, if it exists. Call this only after the deployed
    stack is deleted, because its revisions read code from the bucket.

    Returns True if a code bucket stack was deleted.
    """
    code_stack = WebFunctionCodeBucketStack(parent_stack_name)
    try:
        stack = cloudformation_client.describe_stacks(StackName=code_stack.stack_name)["Stacks"][0]
    except ClientError:
        LOG.debug("No Lambda Web Function code bucket stack found for %s", parent_stack_name)
        return False
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
    tags = {t["Key"]: t["Value"] for t in stack.get("Tags", [])}
    if tags.get("ManagedStackSource") != "AwsSamCli":
        LOG.debug("Stack %s was not created by the AWS SAM CLI, not deleting it", code_stack.stack_name)
        return False

    click.echo(f"\t- Deleting Lambda Web Function code bucket stack {code_stack.stack_name}")
    bucket_name = outputs.get(CODE_BUCKET_OUTPUT_KEY)
    if bucket_name:
        _empty_versioned_bucket(s3_client, bucket_name)
    cloudformation_client.delete_stack(StackName=code_stack.stack_name)
    cloudformation_client.get_waiter("stack_delete_complete").wait(
        StackName=code_stack.stack_name, WaiterConfig={"Delay": 5, "MaxAttempts": 120}
    )
    return True


def _empty_versioned_bucket(s3_client: Any, bucket_name: str) -> None:
    """Delete every object version and delete marker in the bucket."""
    paginator = s3_client.get_paginator("list_object_versions")
    try:
        for page in paginator.paginate(Bucket=bucket_name):
            objects = [
                {"Key": item["Key"], "VersionId": item["VersionId"]}
                for item in page.get("Versions", []) + page.get("DeleteMarkers", [])
            ]
            # delete_objects accepts at most 1000 keys, which is also the page size
            if objects:
                s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects, "Quiet": True})
    except ClientError as ex:
        if ex.response.get("Error", {}).get("Code") == "NoSuchBucket":
            return
        raise
