"""
Script for setting up test resources, ECR login, and credential management.

Usage: python3.11 tests/setup_testing_resources.py [--test-suite <name>] [--container-runtime <docker|finch>]

Behavior:
  - If test suite requires credentials: fetches test credentials and resources
  - For all suites: logs in to Public ECR (with retry)
  - If test suite does NOT require credentials: clears credentials and sets SKIP_ACCOUNT_RESET
"""

import json
import os
import platform
import re
import subprocess
import sys
import time

from datetime import datetime, timezone
from get_testing_resources import get_testing_credentials, get_managed_test_resource_outputs  # type: ignore[import-not-found]  # noqa: E402

from boto3.session import Session

GITHUB_ENV_FILE = os.environ.get("GITHUB_ENV")

# Test suites that do NOT require AWS credentials
NO_CREDENTIAL_SUITES = {
    "build-x86-1",
    "build-x86-2",
    "build-arm64",
    "build-x86-container-1",
    "build-x86-container-2",
    "build-arm64-container-1",
    "build-arm64-container-2",
    "local-invoke",
    "local-start-api",
    "local-start-lambda",
}

# New entries must also be added to MSYS2_ENV_CONV_EXCL in integration-tests.yml.
SENSITIVE_CREDENTIAL_KEYS = {
    "accessKeyID": "AWS_ACCESS_KEY_ID",
    "secretAccessKey": "AWS_SECRET_ACCESS_KEY",
    "sessionToken": "AWS_SESSION_TOKEN",
    "taskToken": "TASK_TOKEN",
}

# Access key ids are uppercase alphanumeric; secrets and session tokens are base64.
CREDENTIAL_PATTERNS = {
    "AWS_ACCESS_KEY_ID": re.compile(r"^[A-Z0-9]{16,128}$"),
    "AWS_SECRET_ACCESS_KEY": re.compile(r"^[A-Za-z0-9+/=]{16,}$"),
    "AWS_SESSION_TOKEN": re.compile(r"^[A-Za-z0-9+/=_-]{16,}$"),
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


def ecr_login(container_runtime: str, retries: int = 3, delay: int = 10):
    """Log in to Public ECR with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            token_result = subprocess.run(
                ["aws", "ecr-public", "get-login-password", "--region", "us-east-1"],
                capture_output=True,
                text=True,
                check=True,
            )
            token = token_result.stdout.strip()

            if container_runtime == "finch":
                login_cmd = ["sudo", "finch", "login", "--username", "AWS", "--password-stdin", "public.ecr.aws"]
            else:
                login_cmd = ["docker", "login", "--username", "AWS", "--password-stdin", "public.ecr.aws"]

            subprocess.run(login_cmd, input=token, text=True, check=True)
            print(f"Successfully logged in to Public ECR via {container_runtime}.")
            return
        except subprocess.CalledProcessError as e:
            print(f"ECR login attempt {attempt}/{retries} failed: {e}", file=sys.stderr)
            if attempt < retries:
                print(f"Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"FATAL: ECR login failed after {retries} attempts.", file=sys.stderr)
                sys.exit(1)


def check_credential(name, value):
    """Windows only: raise if a credential is not credential-shaped, i.e. it was rewritten.

    Git Bash on Windows rewrites env values that look like POSIX paths, so a secret
    beginning with "/" arrives as "C:/Program Files/Git/...". Charset bounds are generous
    because AWS does not guarantee key formats; whitespace and ":" are what the rewrite
    introduces and neither can occur in a real credential.

    Gated to Windows because that is the only platform where the rewrite happens. These
    patterns encode a format AWS does not promise, so running them elsewhere would risk
    failing every suite on every OS for no diagnostic gain.

    Catches the "/x" -> "C:/Program Files/Git/x" form. The "//x" -> "/x" form cannot be
    caught here: once exempted, a real secret may legitimately begin with "/", so the two
    are identical by value and rejecting a leading separator would fail a valid credential.
    warn_leading_separator() reports that case where the value is still pristine.
    """
    if platform.system() != "Windows":
        return
    pattern = CREDENTIAL_PATTERNS.get(name.replace("CI_ACCESS_ROLE_", ""))
    if pattern and not pattern.fullmatch(value):
        raise RuntimeError(
            f"{name} is not a valid AWS credential (length {len(value)}); it was most likely "
            f"rewritten in transit. Ensure {name} is listed in MSYS2_ENV_CONV_EXCL in "
            ".github/workflows/integration-tests.yml. Value not shown -- it is a secret."
        )


def check_conversion_exemptions():
    """Fail loudly if a credential variable is missing from MSYS2_ENV_CONV_EXCL."""
    if platform.system() != "Windows":
        return
    exempt = set(os.environ.get("MSYS2_ENV_CONV_EXCL", "").split(";"))
    if "*" in exempt:
        return
    names = set(SENSITIVE_CREDENTIAL_KEYS.values()) | {
        f"CI_ACCESS_ROLE_{k}" for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
    }
    missing = sorted(names - exempt)
    if missing:
        raise RuntimeError(
            f"These credential variables are not exempt from MSYS2 path conversion: {missing}. "
            "Add them to MSYS2_ENV_CONV_EXCL in .github/workflows/integration-tests.yml, or a "
            "value beginning with '/' will be silently rewritten into a Windows path."
        )


def warn_leading_separator(env_vars):
    """Flag vended credentials that begin with "/" while the value is still pristine.

    Such a value is only safe because MSYS2_ENV_CONV_EXCL exempts it; if that exemption ever
    stops working the failure is an opaque SignatureDoesNotMatch, so leave a breadcrumb here.
    Not an error: this shape is valid and occurs for roughly 1 in 64 secrets.
    """
    if platform.system() != "Windows":
        return
    for json_key, env_name in SENSITIVE_CREDENTIAL_KEYS.items():
        if str(env_vars.get(json_key, "")).startswith("/"):
            print(
                f"[DEBUG] {env_name} begins with '/'; it relies on MSYS2_ENV_CONV_EXCL in "
                ".github/workflows/integration-tests.yml to survive Git Bash path conversion."
            )


def setup_credentials():
    """Fetch and export test credentials and resources."""
    check_conversion_exemptions()

    # Save current CI role credentials for later reset
    for env_key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        value = os.environ.get(env_key, "")
        if value:
            mask_value(value)
            check_credential(env_key, value)
            write_env(f"CI_ACCESS_ROLE_{env_key}", value)

    # Log system clock for debugging InvalidSignatureException on Windows
    print(f"[DEBUG] System clock UTC: {datetime.now(timezone.utc).isoformat()}")

    # Get test credentials with retry for transient OIDC propagation issues
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            try:
                env_vars = get_testing_credentials(skip_role_deletion=True)
            except Exception:
                print("First attempt with skip_role_deletion failed, trying without parameter...")
                env_vars = get_testing_credentials(skip_role_deletion=False)
            break
        except Exception as e:
            if attempt < max_retries:
                print(f"Credential fetch attempt {attempt}/{max_retries} failed: {e}", file=sys.stderr)
                print(f"[DEBUG] System clock UTC: {datetime.now(timezone.utc).isoformat()}")
                print(f"Retrying in 5s...")
                time.sleep(5)
            else:
                print(f"FATAL: Failed to get credentials after {max_retries} attempts.", file=sys.stderr)
                raise

    # Get managed test resources
    test_session = Session(
        aws_access_key_id=env_vars["accessKeyID"],
        aws_secret_access_key=env_vars["secretAccessKey"],
        aws_session_token=env_vars["sessionToken"],
    )
    env_vars.update(get_managed_test_resource_outputs(test_session))
    warn_leading_separator(env_vars)

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


def clear_credentials():
    """Clear credentials and mark account reset as skipped."""
    write_env("SKIP_ACCOUNT_RESET", "true")
    write_env("AWS_ACCESS_KEY_ID", "")
    write_env("AWS_SECRET_ACCESS_KEY", "")
    write_env("AWS_SESSION_TOKEN", "")
    print("Credentials cleared; account reset will be skipped.")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--test-suite", default=os.environ.get("TEST_SUITE", ""))
    parser.add_argument("--container-runtime", default=os.environ.get("CONTAINER_RUNTIME", "docker"))
    args = parser.parse_args()

    if not GITHUB_ENV_FILE:
        print("ERROR: GITHUB_ENV is not set. This script must run inside GitHub Actions.", file=sys.stderr)
        sys.exit(1)

    needs_credentials = args.test_suite not in NO_CREDENTIAL_SUITES

    if needs_credentials:
        setup_credentials()

    # All suites need ECR login, if needs_credentials -> login with test account, else login with oidc account
    ecr_login(args.container_runtime)

    if not needs_credentials:
        # clear all the credentail from oidc, we don't want any request routed to oidc account
        clear_credentials()


if __name__ == "__main__":
    main()
