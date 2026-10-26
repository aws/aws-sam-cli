"""
Per-stack S3 bucket for AWS::Serverless::WebFunction code.

Revisions read their code from S3 for as long as they exist, so it can't go in the shared managed bucket. SAM CLI
creates the bucket's stack when it's first needed and deletes it after the deployed stack.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import click
from botocore.exceptions import ClientError

from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.managed_cloudformation_stack import StackOutput, manage_stack
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)

CODE_BUCKET_OUTPUT_KEY = "WebFunctionCodeBucket"
# Any Web Function revision in this account
WEB_FUNCTION_REVISION_SOURCE_ARN = "arn:${AWS::Partition}:lambda:*:${AWS::AccountId}:web-function/*/revision/*"


class WebFunctionCodeBucketStack:
    """Names the code bucket stack of a deployed stack."""

    def __init__(self, parent_stack_name: str) -> None:
        self.parent_stack_name = parent_stack_name
        # 128 character stack name limit: 100 + 1 + 8 + 16
        self.stack_name = f"{parent_stack_name[:100]}-{str_checksum(parent_stack_name)[:8]}-WebFunctionCode"
        # Unique per account and Region. Importing it stops CloudFormation deleting this stack while it's in use
        self.export_name = f"{self.stack_name}-Bucket"


def get_code_bucket_template(parent_stack_name: str) -> str:
    """Return the code bucket stack's template."""
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
                    # Each revision pins an object version
                    "VersioningConfiguration": {"Status": "Enabled"},
                    # Lambda can't decrypt with the aws/s3 key
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
    """Get or create a stack's code bucket stack; return the bucket name and its export name."""
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


RETAIN_POLICIES = ("Retain", "RetainExceptOnCreate")
NESTED_STACK_TYPES = ("AWS::CloudFormation::Stack", "AWS::Serverless::Application")


def retained_web_functions(
    template_dict: Optional[Dict],
    retain_resources: Optional[list] = None,
    cloudformation_client: Any = None,
    stack_name: Optional[str] = None,
    _all_retained: bool = False,
    _prefix: str = "",
) -> List[str]:
    """
    Paths of Web Functions that outlive the stack (DeletionPolicy: Retain, or in retain_resources), including those
    in nested stacks when cloudformation_client and stack_name are given. Their revisions still read from the code
    bucket. Call before the stack is deleted, while its nested stacks can still be read.
    """
    resources = template_dict.get("Resources") if isinstance(template_dict, dict) else None
    if not isinstance(resources, dict):
        return []
    retain = set(retain_resources or [])
    retained: List[str] = []
    for logical_id, resource in resources.items():
        if not isinstance(resource, dict):
            continue
        is_retained = _all_retained or resource.get("DeletionPolicy") in RETAIN_POLICIES
        if resource.get("Type") == "AWS::Serverless::WebFunction":
            if is_retained or {logical_id, f"{logical_id}Revision", f"{logical_id}Endpoint"} & retain:
                retained.append(f"{_prefix}{logical_id}")
        elif resource.get("Type") in NESTED_STACK_TYPES and cloudformation_client and stack_name:
            child_stack, child_template = _nested_stack(cloudformation_client, stack_name, logical_id)
            if child_template is None:
                # Can't tell whether it has Web Functions, so keep the code bucket to be safe
                retained.append(f"{_prefix}{logical_id}")
            elif child_stack:
                retained.extend(
                    retained_web_functions(
                        child_template,
                        cloudformation_client=cloudformation_client,
                        stack_name=child_stack,
                        _all_retained=is_retained or logical_id in retain,
                        _prefix=f"{_prefix}{logical_id}/",
                    )
                )
    return retained


def _nested_stack(cloudformation_client: Any, stack_name: str, logical_id: str) -> Tuple[Optional[str], Optional[Dict]]:
    """Return a nested stack's ID and original template: ("", {}) if it wasn't created, (None, None) if unreadable"""
    try:
        detail = cloudformation_client.describe_stack_resource(StackName=stack_name, LogicalResourceId=logical_id)
        child_stack = detail["StackResourceDetail"].get("PhysicalResourceId")
        if not child_stack:
            return "", {}
        body = cloudformation_client.get_template(StackName=child_stack, TemplateStage="Original")["TemplateBody"]
        return child_stack, body if isinstance(body, dict) else yaml_parse(body)
    except ClientError as ex:
        if "does not exist" in str(ex):
            return "", {}
        LOG.debug("Could not read nested stack %s of %s", logical_id, stack_name, exc_info=ex)
    except Exception as ex:  # pylint: disable=broad-except
        LOG.debug("Could not read nested stack %s of %s", logical_id, stack_name, exc_info=ex)
    return None, None


def _export_importers(cloudformation_client: Any, export_name: str) -> List[str]:
    """Stacks that import the export"""
    try:
        return list(cloudformation_client.list_imports(ExportName=export_name).get("Imports", []))
    except ClientError as ex:
        if "is not imported" in str(ex):
            return []
        raise


# Results of delete_web_function_code_bucket
CODE_BUCKET_DELETED = "deleted"
CODE_BUCKET_NOT_FOUND = "not_found"
CODE_BUCKET_PROTECTED = "protected"


def keep_web_function_code_bucket(
    parent_stack_name: str, retained: List[str], cloudformation_client: Any, reason: str = "Web Functions"
) -> None:
    """Keep the code bucket stack for retained Web Functions, with termination protection on."""
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
        f"\n\tKept Lambda Web Function code bucket stack {code_stack.stack_name}, because these {reason} are "
        f"retained and still read their code from it: {', '.join(retained)}. {protection}When you no longer need "
        "them, turn off its termination protection, empty its bucket and delete the stack.",
        fg="yellow",
    )


def delete_web_function_code_bucket(parent_stack_name: str, cloudformation_client: Any, s3_client: Any) -> str:
    """
    Empty and delete a stack's code bucket stack. Call only after the deployed stack is deleted.

    Returns CODE_BUCKET_DELETED, CODE_BUCKET_NOT_FOUND, or CODE_BUCKET_PROTECTED (termination protection is on).
    """
    code_stack = WebFunctionCodeBucketStack(parent_stack_name)
    try:
        stack = cloudformation_client.describe_stacks(StackName=code_stack.stack_name)["Stacks"][0]
    except ClientError as ex:
        # Raise anything but a missing stack, so the bucket isn't silently left behind
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

    # A stack that outlives the deleted one, like a retained nested stack, still reads code from the bucket
    importers = _export_importers(cloudformation_client, code_stack.export_name)
    if importers:
        keep_web_function_code_bucket(parent_stack_name, importers, cloudformation_client, reason="importing stacks")
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
            # delete_objects takes at most 1000 keys
            if objects:
                s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects, "Quiet": True})
    except ClientError as ex:
        if ex.response.get("Error", {}).get("Code") == "NoSuchBucket":
            return
        raise
