"""
Utils for gathering system related info, mainly for use in `sam --info`
"""

import json
from typing import Dict, cast


def gather_system_info() -> Dict[str, str]:
    """
    Gather system info

    Returns
    -------
    dict[str, str]
    """
    from platform import platform, python_version

    info = {
        "python": python_version(),
        "os": platform(),
    }
    return info


def gather_additional_dependencies_info() -> Dict[str, str]:
    """
    Gather additional depedencies info

    Returns
    -------
    dict[str, str]
        A dictionary with the key representing the info we need
        and value being the version number
    """
    info = {
        "docker_engine": _gather_docker_info(),
        "aws_cdk": _gather_cdk_info(),
        "terraform": _gather_terraform_info(),
    }
    return info


def _gather_docker_info() -> str:
    """
    Get Docker Engine version

    Returns
    -------
    str
        Version number of Docker Engine if available. Otherwise "Not available"
    """
    import contextlib

    import docker

    from samcli.lib.constants import DOCKER_MIN_API_VERSION
    from samcli.local.docker.utils import is_docker_reachable

    with contextlib.closing(docker.from_env(version=DOCKER_MIN_API_VERSION)) as client:
        if is_docker_reachable(client):
            return cast(str, client.version().get("Version", "Not available"))
        return "Not available"


def _gather_cdk_info():
    """
    Get AWS CDK version numbner.

    AWS SAM CLI does not invoke CDK, but only uses the CFN templates generated from `cdk synth`.
    Knowing the CDK version number will help us diagnose if any issue is caused by a new version of CDK.

    Returns
    -------
    str
        Version number of AWS CDK if available, e.g. "2.20.0 (build 738ef49)"
        Otherwise "Not available"
    """
    import subprocess

    try:
        process = subprocess.run(["cdk", "--version"], capture_output=True, text=True, check=True)
        return process.stdout.strip()
    except Exception:
        return "Not available"


def _gather_terraform_info():
    """
    Get Terraform version numbner.

    AWS SAM CLI invokes Terraform for Terraform applications.
    Knowing the Terraform version number will help us diagnose if any issue is caused by a new version of Terraform.

    Returns
    -------
    str
        Version number of Terraform if available, e.g. "1.2.1"
        Otherwise "Not available"
    """
    import subprocess

    try:
        process = subprocess.run(["terraform", "version", "-json"], capture_output=True, text=True, check=True)
        info_dict = json.loads(process.stdout)
        return info_dict.get("terraform_version", "Not available")
    except Exception:
        return "Not available"
