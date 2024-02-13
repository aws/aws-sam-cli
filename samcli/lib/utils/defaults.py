"""
Contains helpers for providing default values
"""

from botocore.session import get_session


def get_default_aws_region() -> str:
    return get_session().get_config_variable("region") or "us-east-1"
