"""
Checks that an S3 bucket can hold AWS::Serverless::WebFunction code.

Lambda reads the code as lambda.amazonaws.com, so the bucket must be versioned and readable by it, and an SSE-KMS key
must be customer managed and let it decrypt. An unversioned bucket or AWS managed key fails packaging; other problems
are warnings, since they can't be fully evaluated here.
"""

import fnmatch
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import click
from botocore.exceptions import ClientError

from samcli.commands.exceptions import UserException

LOG = logging.getLogger(__name__)

LAMBDA_SERVICE_PRINCIPAL = "lambda.amazonaws.com"
REQUIRED_S3_ACTIONS = ("s3:GetObject", "s3:GetObjectVersion")
EXAMPLE_POLICY_DOCS = (
    "https://docs.aws.amazon.com/lambda/latest/dg/web-functions-code-s3.html#web-functions-code-s3-bucket-policy"
)


class WebFunctionCodeBucketError(UserException):
    """Lambda can't read Web Function code from the bucket or KMS key."""

    def __init__(self, problems: List[str]):
        problem_lines = "\n".join(f"- {problem}" for problem in problems)
        super().__init__(message=f"Lambda Web Functions can't read code uploaded with these settings:\n{problem_lines}")


def check_web_function_code_bucket(
    s3_client: Any,
    bucket: str,
    prefix: Optional[str] = None,
    kms_key_id: Optional[str] = None,
    kms_client: Optional[Any] = None,
) -> List[str]:
    """
    Check that the bucket can serve Web Function code. Raises WebFunctionCodeBucketError for an unversioned bucket or an
    AWS managed key; prints other problems to stderr as warnings and returns them.
    """
    errors: List[str] = []
    warnings: List[str] = []
    for check_errors, check_warnings in (
        _check_versioning(s3_client, bucket),
        _check_bucket_policy(s3_client, bucket, prefix),
        _check_kms_key(kms_client, kms_key_id) if kms_key_id and kms_client is not None else ([], []),
    ):
        errors.extend(check_errors)
        warnings.extend(check_warnings)
    for warning in warnings:
        click.secho(f"\n\tWarning: {warning}", fg="yellow", err=True)
    if errors:
        raise WebFunctionCodeBucketError(errors)
    return warnings


def _check_versioning(s3_client: Any, bucket: str) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings)."""
    try:
        status = s3_client.get_bucket_versioning(Bucket=bucket).get("Status")
    except ClientError as ex:
        LOG.debug("Could not read versioning for bucket %s", bucket, exc_info=ex)
        return [], [
            f"Couldn't check that S3 bucket {bucket} has versioning enabled, which Lambda Web Functions require."
        ]
    if status != "Enabled":
        return [
            f"S3 bucket {bucket} doesn't have versioning enabled. Lambda Web Functions require a versioned code "
            "bucket; enable versioning on it or use another bucket."
        ], []
    return [], []


def _check_bucket_policy(s3_client: Any, bucket: str, prefix: Optional[str]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings). Policy problems are warnings, since this is a heuristic."""
    missing_message = (
        f"The policy of S3 bucket {bucket} doesn't allow {LAMBDA_SERVICE_PRINCIPAL} to call "
        f"{' and '.join(REQUIRED_S3_ACTIONS)} on the uploaded code, so Lambda Web Functions can't read it. "
        f"For an example policy, see {EXAMPLE_POLICY_DOCS}"
    )
    try:
        policy = json.loads(s3_client.get_bucket_policy(Bucket=bucket)["Policy"])
    except ClientError as ex:
        if ex.response.get("Error", {}).get("Code") == "NoSuchBucketPolicy":
            return [], [missing_message]
        LOG.debug("Could not read the policy of bucket %s", bucket, exc_info=ex)
        return [], [
            f"Couldn't read the policy of S3 bucket {bucket} to check that {LAMBDA_SERVICE_PRINCIPAL} can read "
            "Lambda Web Function code."
        ]
    key = f"{prefix.strip('/')}/code" if prefix else "code"
    if all(_policy_allows(policy, action, bucket, key) for action in REQUIRED_S3_ACTIONS):
        return [], []
    return [], [missing_message]


def _check_kms_key(kms_client: Any, kms_key_id: str) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings). An AWS managed key is an error; key policy problems are warnings."""
    try:
        metadata = kms_client.describe_key(KeyId=kms_key_id)["KeyMetadata"]
    except ClientError as ex:
        LOG.debug("Could not describe KMS key %s", kms_key_id, exc_info=ex)
        return [], [
            f"Couldn't check KMS key {kms_key_id}, which Lambda must be able to use to decrypt Web Function code."
        ]
    if metadata.get("KeyManager") == "AWS":
        return [
            f"KMS key {kms_key_id} is an AWS managed key. Lambda Web Functions can't read code encrypted with it; use "
            f"a customer managed key whose key policy allows {LAMBDA_SERVICE_PRINCIPAL} to call kms:Decrypt."
        ], []
    try:
        policy = json.loads(kms_client.get_key_policy(KeyId=metadata["KeyId"], PolicyName="default")["Policy"])
    except ClientError as ex:
        LOG.debug("Could not read the policy of KMS key %s", kms_key_id, exc_info=ex)
        return [], [f"Couldn't read the policy of KMS key {kms_key_id} to check that Lambda can decrypt with it."]
    if not _policy_allows(policy, "kms:Decrypt"):
        return [], [
            f"The policy of KMS key {kms_key_id} doesn't allow {LAMBDA_SERVICE_PRINCIPAL} to call kms:Decrypt, so "
            "Lambda Web Functions can't read code encrypted with it."
        ]
    return [], []


def _policy_allows(policy: Dict[str, Any], action: str, bucket: Optional[str] = None, key: str = "") -> bool:
    """
    Whether an Allow statement grants the action to the Lambda service principal. Conditions aren't evaluated; for S3,
    the Resource must match an object under the key.
    """
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    for statement in statements:
        if not isinstance(statement, dict) or statement.get("Effect") != "Allow":
            continue
        if not _principal_includes_lambda(statement.get("Principal")):
            continue
        if not any(
            fnmatch.fnmatchcase(action.lower(), pattern.lower()) for pattern in _as_list(statement.get("Action"))
        ):
            continue
        if bucket is None or any(
            _resource_matches(pattern, bucket, key) for pattern in _as_list(statement.get("Resource"))
        ):
            return True
    return False


def _principal_includes_lambda(principal: Any) -> bool:
    if principal == "*":
        return True
    if isinstance(principal, dict):
        return "*" in _as_list(principal.get("AWS")) or LAMBDA_SERVICE_PRINCIPAL in _as_list(principal.get("Service"))
    return False


def _resource_matches(pattern: str, bucket: str, key: str) -> bool:
    if pattern == "*":
        return True
    parts = pattern.split(":", 5)
    if len(parts) != 6 or parts[0] != "arn" or parts[2] != "s3":  # noqa: PLR2004
        return False
    return fnmatch.fnmatchcase(f"{bucket}/{key}", parts[5])


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
