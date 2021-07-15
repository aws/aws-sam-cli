"""
This module contains utility functions for boto3 library
"""
from typing import Any
from typing_extensions import Protocol

import boto3
from botocore.config import Config

from samcli import __version__
from samcli.cli.global_config import GlobalConfig


def get_boto_config_with_user_agent(**kwargs) -> Config:
    """
    Automatically add user agent string to boto configs.

    Parameters
    ----------
    kwargs :
        key=value params which will be added to the Config object

    Returns
    -------
    Config
        Returns config instance which contains given parameters in it
    """
    gc = GlobalConfig()
    return Config(
        user_agent_extra=f"aws-sam-cli/{__version__}/{gc.installation_id}"
        if gc.telemetry_enabled
        else f"aws-sam-cli/{__version__}",
        **kwargs,
    )


# Type definition of following boto providers, which is equal to Callable[[str], Any]
class BotoProviderType(Protocol):
    def __call__(self, service_name: str) -> Any:
        ...


def get_boto_client_provider_with_config(**kwargs) -> BotoProviderType:
    """
    Returns a wrapper function for boto client with given configuration. It can be used like;

    client_provider = get_boto_client_wrapper_with_config(region_name=region)
    lambda_client = client_provider("lambda")

    Parameters
    ----------
    kwargs :
        Key-value params that will be passed to get_boto_config_with_user_agent

    Returns
    -------
        A callable function which will return a boto client
    """
    # ignore typing because mypy tries to assert client_name with a valid service name
    return lambda client_name: boto3.session.Session().client(
        client_name, config=get_boto_config_with_user_agent(**kwargs)
    )


def get_boto_resource_provider_with_config(**kwargs) -> BotoProviderType:
    """
    Returns a wrapper function for boto resource with given configuration. It can be used like;

    resource_provider = get_boto_resource_wrapper_with_config(region_name=region)
    cloudformation_resource = resource_provider("cloudformation")

    Parameters
    ----------
    kwargs :
        Key-value params that will be passed to get_boto_config_with_user_agent

    Returns
    -------
        A callable function which will return a boto resource
    """
    # ignore typing because mypy tries to assert client_name with a valid service name
    return lambda resource_name: boto3.session.Session().resource(
        resource_name, config=get_boto_config_with_user_agent(**kwargs)
    )
