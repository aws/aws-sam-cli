"""
This module contains utility functions for boto3 library
"""
from typing import Any, Optional

from boto3 import Session
from botocore.config import Config
from botocore.exceptions import ClientError
from typing_extensions import Protocol

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
        ...  # pragma: no cover


def get_boto_client_provider_from_session_with_config(session: Session, **kwargs) -> BotoProviderType:
    """
    Returns a wrapper function for boto client with given configuration. It can be used like;

    client_provider = get_boto_client_wrapper_with_config(session=session)
    lambda_client = client_provider("lambda")

    Parameters
    ----------
    session: Session
        Boto3 session object
    kwargs :
        Key-value params that will be passed to get_boto_config_with_user_agent

    Returns
    -------
        A callable function which will return a boto client
    """
    return lambda client_name: session.client(client_name, config=get_boto_config_with_user_agent(**kwargs))


def get_boto_client_provider_with_config(
    region: Optional[str] = None, profile: Optional[str] = None, **kwargs
) -> BotoProviderType:
    """
    Returns a wrapper function for boto client with given configuration. It can be used like;

    client_provider = get_boto_client_wrapper_with_config(region_name=region)
    lambda_client = client_provider("lambda")

    Parameters
    ----------
    region: Optional[str]
        AWS region name
    profile: Optional[str]
        Profile name from credentials
    kwargs :
        Key-value params that will be passed to get_boto_config_with_user_agent

    Returns
    -------
        A callable function which will return a boto client
    """
    return get_boto_client_provider_from_session_with_config(
        Session(region_name=region, profile_name=profile), **kwargs
    )


def get_boto_resource_provider_from_session_with_config(session: Session, **kwargs) -> BotoProviderType:
    """
    Returns a wrapper function for boto resource with given configuration. It can be used like;

    resource_provider = get_boto_resource_wrapper_with_config(session=session)
    cloudformation_resource = resource_provider("cloudformation")

    Parameters
    ----------
    session: Session
        Boto3 session object
    kwargs :
        Key-value params that will be passed to get_boto_config_with_user_agent

    Returns
    -------
        A callable function which will return a boto resource
    """
    return lambda resource_name: session.resource(resource_name, config=get_boto_config_with_user_agent(**kwargs))


def get_boto_resource_provider_with_config(
    region: Optional[str] = None, profile: Optional[str] = None, **kwargs
) -> BotoProviderType:
    """
    Returns a wrapper function for boto resource with given configuration. It can be used like;

    resource_provider = get_boto_resource_wrapper_with_config(region_name=region)
    cloudformation_resource = resource_provider("cloudformation")

    Parameters
    ----------
    region: Optional[str]
        AWS region name
    profile: Optional[str]
        Profile name from credentials
    kwargs :
        Key-value params that will be passed to get_boto_config_with_user_agent

    Returns
    -------
        A callable function which will return a boto resource
    """
    return get_boto_resource_provider_from_session_with_config(
        Session(region_name=region, profile_name=profile), **kwargs
    )


def get_client_error_code(client_error: ClientError) -> Optional[str]:
    """Extracts error code from boto ClientError"""
    return client_error.response.get("Error", {}).get("Code")
