"""
Script for resetting the test account after integration tests.
Switches back to CI role credentials and invokes the account reset Lambda.

Usage: python3.11 tests/reset_testing_resources.py
"""

import json
import os
import sys

import boto3
from botocore.config import Config


def main():
    # Switch back to CI access role credentials
    access_key = os.environ.get("CI_ACCESS_ROLE_AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("CI_ACCESS_ROLE_AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("CI_ACCESS_ROLE_AWS_SESSION_TOKEN")
    task_token = os.environ.get("TASK_TOKEN")
    lambda_arn = os.environ.get("ACCOUNT_RESET_LAMBDA_ARN")

    if not all([access_key, secret_key, session_token, task_token, lambda_arn]):
        print("ERROR: Missing required environment variables for account reset.", file=sys.stderr)
        sys.exit(1)

    lambda_client = boto3.client(
        "lambda",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name="us-west-2",
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )

    payload = json.dumps({"taskToken": task_token, "output": "{}"})
    response = lambda_client.invoke(
        FunctionName=lambda_arn,
        Payload=payload,
    )

    response_payload = response["Payload"].read().decode("utf-8")
    print(response_payload)

    if response.get("FunctionError"):
        print("ERROR: Account reset Lambda returned an error.", file=sys.stderr)
        sys.exit(1)

    print("Account reset completed successfully.")


if __name__ == "__main__":
    main()
