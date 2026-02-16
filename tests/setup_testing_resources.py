"""
Script for getting test account credentials and managed test account resources,
then exporting them as masked GitHub Actions environment variables.

Usage: python3.11 tests/setup_testing_resources.py
"""

import json
import os
import sys

from get_testing_resources import get_testing_credentials, get_managed_test_resource_outputs

from boto3.session import Session


GITHUB_ENV_FILE = os.environ.get("GITHUB_ENV")

SENSITIVE_CREDENTIAL_KEYS = {
    "accessKeyID": "AWS_ACCESS_KEY_ID",
    "secretAccessKey": "AWS_SECRET_ACCESS_KEY",
    "sessionToken": "AWS_SESSION_TOKEN",
    "taskToken": "TASK_TOKEN",
}

RESOURCE_KEYS = {
    "TestBucketName": "AWS_S3_TESTING",
    "TestECRURI": "AWS_ECR_TESTING",
    "TestKMSKeyArn": "AWS_KMS_KEY",
    "TestSigningProfileName": "AWS_SIGNING_PROFILE_NAME",
    "TestSigningProfileARN": "AWS_SIGNING_PROFILE_VERSION_ARN",
    "LMISubnetId": "LMI_SUBNET_ID",
    "LMISecurityGroupId": "LMI_SECURITY_GROUP_ID",
}


def mask_value(value):
    """Mask a value so it doesn't appear in GitHub Actions logs."""
    print(f"::add-mask::{value}")


def write_env(name, value):
    """Write an environment variable to GITHUB_ENV."""
    with open(GITHUB_ENV_FILE, "a") as f:
        f.write(f"{name}={value}\n")


def main():
    if not GITHUB_ENV_FILE:
        print("ERROR: GITHUB_ENV is not set. This script must run inside GitHub Actions.", file=sys.stderr)
        sys.exit(1)

    # Save current CI role credentials for later reset
    for env_key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        value = os.environ.get(env_key, "")
        if value:
            mask_value(value)
            write_env(f"CI_ACCESS_ROLE_{env_key}", value)

    # Get test credentials (try skip_role_deletion first)
    try:
        env_vars = get_testing_credentials(skip_role_deletion=True)
    except Exception:
        print("First attempt with skip_role_deletion failed, trying without parameter...")
        env_vars = get_testing_credentials(skip_role_deletion=False)

    # Get managed test resources
    test_session = Session(
        aws_access_key_id=env_vars["accessKeyID"],
        aws_secret_access_key=env_vars["secretAccessKey"],
        aws_session_token=env_vars["sessionToken"],
    )
    env_vars.update(get_managed_test_resource_outputs(test_session))

    # Export sensitive credentials (masked)
    for json_key, env_name in SENSITIVE_CREDENTIAL_KEYS.items():
        value = env_vars.get(json_key, "")
        if value:
            mask_value(value)
            write_env(env_name, value)

    # Export resource values
    for json_key, env_name in RESOURCE_KEYS.items():
        value = env_vars.get(json_key, "")
        write_env(env_name, value)

    print("Testing resources and credentials exported successfully.")


if __name__ == "__main__":
    main()
