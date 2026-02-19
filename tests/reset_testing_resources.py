"""
Script for post-test cleanup: uploads test reports to S3 and optionally resets the test account.

Usage: python3.11 tests/reset_testing_resources.py <test_suite_name>

Environment variables:
  SKIP_ACCOUNT_RESET       - Set to "true" to skip account reset (local-only jobs)
  TESTREPORTING_ARN        - Role ARN to assume for S3 upload
  TESTREPORTING_S3         - S3 bucket name for test reports
  GITHUB_RUN_ID            - GitHub Actions run ID
  CI_ACCESS_ROLE_*         - CI role credentials for account reset and role assumption
  TASK_TOKEN               - Task token for account reset Lambda
  ACCOUNT_RESET_LAMBDA_ARN - Lambda ARN for account reset
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

import boto3
from botocore.config import Config

DEFAULT_BOTO_CONFIG = Config(retries={"max_attempts": 3, "mode": "standard"})


def _get_ci_role_credentials():
    """Get the saved CI role credentials, or None if not available."""
    access_key = os.environ.get("CI_ACCESS_ROLE_AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("CI_ACCESS_ROLE_AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("CI_ACCESS_ROLE_AWS_SESSION_TOKEN")
    if access_key and secret_key:
        return {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "aws_session_token": session_token,
        }
    return None


def upload_test_reports(test_suite):
    """Upload test report JSON files to S3 via assumed reporting role."""
    reporting_role_arn = os.environ.get("TESTREPORTING_ARN")
    reporting_s3_bucket = os.environ.get("TESTREPORTING_S3")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")

    if not reporting_role_arn or not reporting_s3_bucket:
        print("TESTREPORTING_ARN or TESTREPORTING_S3 not set, skipping report upload.")
        return

    reports = glob.glob("TEST_REPORT-*.json")
    if not reports:
        print("No test report files found.")
        return

    # Use CI role credentials or fall back to default (OIDC)
    ci_creds = _get_ci_role_credentials()
    sts_kwargs = ci_creds if ci_creds else {}
    sts_client = boto3.client("sts", config=DEFAULT_BOTO_CONFIG, **sts_kwargs)

    try:
        response = sts_client.assume_role(
            RoleArn=reporting_role_arn,
            RoleSessionName=f"test-report-{test_suite}"[:64],
        )
        creds = response["Credentials"]

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            config=DEFAULT_BOTO_CONFIG,
        )

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        s3_prefix = f"github/{date_str}/{run_id}"

        for report_path in reports:
            s3_key = f"{s3_prefix}/{report_path}"
            s3_client.upload_file(report_path, reporting_s3_bucket, s3_key)
            print(f"Uploaded {report_path} to s3://{reporting_s3_bucket}/{s3_key}")

        print(f"Uploaded {len(reports)} report(s) successfully.")
    except Exception as e:
        print(f"WARNING: Failed to upload test reports: {e}", file=sys.stderr)


def reset_test_account():
    """Reset the test account by invoking the account reset Lambda."""
    if os.environ.get("SKIP_ACCOUNT_RESET") == "true":
        print("SKIP_ACCOUNT_RESET is set, skipping account reset.")
        return

    ci_creds = _get_ci_role_credentials()
    task_token = os.environ.get("TASK_TOKEN")
    lambda_arn = os.environ.get("ACCOUNT_RESET_LAMBDA_ARN")

    if not ci_creds or not task_token or not lambda_arn:
        print("Missing credentials or config for account reset, skipping.", file=sys.stderr)
        return

    lambda_client = boto3.client(
        "lambda",
        region_name="us-west-2",
        config=DEFAULT_BOTO_CONFIG,
        **ci_creds,
    )

    payload = json.dumps({"taskToken": task_token, "output": "{}"})
    response = lambda_client.invoke(FunctionName=lambda_arn, Payload=payload)

    response_payload = response["Payload"].read().decode("utf-8")
    print(response_payload)

    if response.get("FunctionError"):
        print("ERROR: Account reset Lambda returned an error.", file=sys.stderr)
        sys.exit(1)

    print("Account reset completed successfully.")


def main():
    test_suite = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    # Always upload test reports
    upload_test_reports(test_suite)

    # Reset account unless skipped
    reset_test_account()


if __name__ == "__main__":
    main()
