"""
Per-stack S3 bucket for AWS::Serverless::WebFunction code.

Lambda Web Functions read their code from S3 for as long as a revision exists, so the code can't live in the shared
managed bucket, which users can empty or delete without affecting Event Functions. Each deployed stack that has a
Web Function with local code gets its own bucket, in a stack that SAM CLI creates the first time it's needed and
deletes after the deployed stack is deleted.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

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
        # Unique per account and Region because the stack name is. Packaged templates import it, so CloudFormation
        # won't delete the code bucket stack while a stack that reads code from it exists.
        self.export_name = f"{self.stack_name}-Bucket"


def get_code_bucket_template(parent_stack_name: str) -> str:
    """Return the template of the code bucket stack."""
    export_name = WebFunctionCodeBucketStack(parent_stack_name).export_name
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
        "Outputs": {CODE_BUCKET_OUTPUT_KEY: {"Value": {"Ref": "CodeBucket"}, "Export": {"Name": export_name}}},
    }
    return json.dumps(template)


def manage_web_function_code_bucket(
    parent_stack_name: str, region: Optional[str], profile: Optional[str]
) -> Tuple[str, str]:
    """
    Get or create the code bucket stack of a deployed stack, and return the bucket name and the name of the export
    that holds it.
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
    return bucket_name, code_stack.export_name


def retained_web_functions(template_dict: Optional[Dict], retain_resources: Optional[list] = None) -> List[str]:
    """
    Return the logical IDs of the template's AWS::Serverless::WebFunction resources that outlive the stack, because
    their DeletionPolicy retains them or they're in retain_resources. Their revisions keep reading code from the code
    bucket, so it must not be deleted.
    """
    resources = template_dict.get("Resources") if isinstance(template_dict, dict) else None
    if not isinstance(resources, dict):
        return []
    retain = set(retain_resources or [])
    retained: List[str] = []
    for logical_id, resource in resources.items():
        if not isinstance(resource, dict) or resource.get("Type") != "AWS::Serverless::WebFunction":
            continue
        generated_ids = {logical_id, f"{logical_id}Revision", f"{logical_id}Endpoint"}
        if resource.get("DeletionPolicy") in ("Retain", "RetainExceptOnCreate") or generated_ids & retain:
            retained.append(logical_id)
    return retained


# Results of delete_web_function_code_bucket
CODE_BUCKET_DELETED = "deleted"
CODE_BUCKET_NOT_FOUND = "not_found"
CODE_BUCKET_PROTECTED = "protected"


def keep_web_function_code_bucket(parent_stack_name: str, retained: List[str], cloudformation_client: Any) -> None:
    """
    Keep the code bucket stack of a deleted stack whose Web Functions are retained, and turn on termination protection
    so a later sam delete, or a direct CloudFormation delete, leaves it in place.
    """
    code_stack = WebFunctionCodeBucketStack(parent_stack_name)
    try:
        cloudformation_client.update_termination_protection(
            EnableTerminationProtection=True, StackName=code_stack.stack_name
        )
        protection = "Turned on termination protection for it. "
    except ClientError as ex:
        if "does not exist" in str(ex):
            return
        LOG.debug("Could not turn on termination protection for %s", code_stack.stack_name, exc_info=ex)
        protection = "Couldn't turn on termination protection for it, so don't delete it while they're in use. "
    click.secho(
        f"\n\tKept Lambda Web Function code bucket stack {code_stack.stack_name}, because these Web Functions are "
        f"retained and still read their code from it: {', '.join(retained)}. {protection}When you no longer need "
        "them, turn off its termination protection, empty its bucket and delete the stack.",
        fg="yellow",
    )


def delete_web_function_code_bucket(parent_stack_name: str, cloudformation_client: Any, s3_client: Any) -> str:
    """
    Empty and delete the code bucket stack of a deployed stack, if it exists and isn't protected. Call this only
    after the deployed stack is deleted, because its revisions read code from the bucket.

    Returns CODE_BUCKET_DELETED, CODE_BUCKET_NOT_FOUND, or CODE_BUCKET_PROTECTED if termination protection is on,
    which sam delete turns on when it keeps the bucket for retained Web Functions.
    """
    code_stack = WebFunctionCodeBucketStack(parent_stack_name)
    try:
        stack = cloudformation_client.describe_stacks(StackName=code_stack.stack_name)["Stacks"][0]
    except ClientError as ex:
        # Only a missing stack means there's nothing to delete; access, throttling and credential errors are raised
        # so the bucket isn't left behind silently
        if "does not exist" not in str(ex):
            raise
        LOG.debug("No Lambda Web Function code bucket stack found for %s", parent_stack_name)
        return CODE_BUCKET_NOT_FOUND
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
    tags = {t["Key"]: t["Value"] for t in stack.get("Tags", [])}
    if tags.get("ManagedStackSource") != "AwsSamCli":
        LOG.debug("Stack %s was not created by the AWS SAM CLI, not deleting it", code_stack.stack_name)
        return CODE_BUCKET_NOT_FOUND
    if stack.get("EnableTerminationProtection"):
        click.secho(
            f"\n\tKept Lambda Web Function code bucket stack {code_stack.stack_name}, because termination protection "
            "is on: retained Web Functions may still read their code from it. When you no longer need them, turn off "
            "its termination protection, empty its bucket and delete the stack.",
            fg="yellow",
        )
        return CODE_BUCKET_PROTECTED

    click.echo(f"\t- Deleting Lambda Web Function code bucket stack {code_stack.stack_name}")
    bucket_name = outputs.get(CODE_BUCKET_OUTPUT_KEY)
    if bucket_name:
        _empty_versioned_bucket(s3_client, bucket_name)
    cloudformation_client.delete_stack(StackName=code_stack.stack_name)
    cloudformation_client.get_waiter("stack_delete_complete").wait(
        StackName=code_stack.stack_name, WaiterConfig={"Delay": 5, "MaxAttempts": 120}
    )
    return CODE_BUCKET_DELETED


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
