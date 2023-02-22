"""
Read and parse CLI args for the Logs Command and setup the context for running the command
"""

import logging
from typing import Any, Dict, List, Optional, Set

from samcli.commands.exceptions import UserException
from samcli.lib.utils.boto_utils import BotoProviderType
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary, get_resource_summaries
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_LAMBDA_FUNCTION,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)
from samcli.lib.utils.time import parse_date, to_utc

LOG = logging.getLogger(__name__)


class InvalidTimestampError(UserException):
    """
    Used to indicate that given date time string is an invalid timestamp
    """


class TimeParseError(UserException):
    """
    Used to throw if parsing of the given time string or UTC conversion is failed
    """


def parse_time(time_str: str, property_name: str):
    """
    Parse the time from the given string, convert to UTC, and return the datetime object

    Parameters
    ----------
    time_str : str
        The time to parse

    property_name : str
        Name of the property where this time came from. Used in the exception raised if time is not parseable

    Returns
    -------
    datetime.datetime
        Parsed datetime object

    Raises
    ------
    InvalidTimestampError
        If the string cannot be parsed as a timestamp
    """
    try:
        if not time_str:
            return None

        parsed = parse_date(time_str)
        if not parsed:
            raise InvalidTimestampError(f"Unable to parse the time provided by '{property_name}'")

        return to_utc(parsed)
    except InvalidTimestampError as ex:
        raise ex
    except Exception as ex:
        LOG.error("Failed to parse given time information %s", time_str, exc_info=ex)
        raise TimeParseError(f"Unable to parse the time information '{property_name}': '{time_str}'") from ex


class ResourcePhysicalIdResolver:
    """
    Wrapper class that is used to extract information about resources which we can tail their logs for given stack
    """

    # list of resource types that is supported right now for pulling their logs
    DEFAULT_SUPPORTED_RESOURCES: Set[str] = {
        AWS_LAMBDA_FUNCTION,
        AWS_APIGATEWAY_RESTAPI,
        AWS_APIGATEWAY_V2_API,
        AWS_STEPFUNCTIONS_STATEMACHINE,
    }

    def __init__(
        self,
        boto_resource_provider: BotoProviderType,
        boto_client_provider: BotoProviderType,
        stack_name: str,
        resource_names: Optional[List[str]] = None,
        supported_resource_types: Optional[Set[str]] = None,
    ):
        self._boto_resource_provider = boto_resource_provider
        self._boto_client_provider = boto_client_provider
        self._stack_name = stack_name
        if resource_names is None:
            resource_names = []
        if supported_resource_types is None:
            supported_resource_types = ResourcePhysicalIdResolver.DEFAULT_SUPPORTED_RESOURCES
        self._supported_resource_types: Set[str] = supported_resource_types
        self._resource_names = set(resource_names)

    def get_resource_information(self, fetch_all_when_no_resource_name_given: bool = True) -> List[Any]:
        """
        Returns the list of resource information for the given stack.

        Parameters
        ----------
        fetch_all_when_no_resource_name_given : bool
            When given, it will fetch all resources if no specific resource name is provided, default value is True

        Returns
        -------
        List[StackResourceSummary]
            List of resource information, which will be used to fetch the logs
        """
        if self._resource_names:
            return self._fetch_resources_from_stack(self._resource_names)
        if fetch_all_when_no_resource_name_given:
            return self._fetch_resources_from_stack()
        return []

    def _fetch_resources_from_stack(
        self, selected_resource_names: Optional[Set[str]] = None
    ) -> List[CloudFormationResourceSummary]:
        """
        Returns list of all resources from given stack name
        If any resource is not supported, it will discard them

        Parameters
        ----------
        selected_resource_names : Optional[Set[str]]
            An optional set of string parameter, which will filter resource names. If none is given, it will be
            equal to all resource names in stack, which means there won't be any filtering by resource name.

        Returns
        -------
        List[CloudFormationResourceSummary]
            List of resource information, which will be used to fetch the logs
        """
        LOG.debug("Getting logical id of the all resources for stack '%s'", self._stack_name)
        stack_resources = get_resource_summaries(
            self._boto_resource_provider,
            self._boto_client_provider,
            self._stack_name,
            ResourcePhysicalIdResolver.DEFAULT_SUPPORTED_RESOURCES,
        )

        if selected_resource_names:
            return self._get_selected_resources(stack_resources, selected_resource_names)
        return list(stack_resources.values())

    @staticmethod
    def _get_selected_resources(
        resource_summaries: Dict[str, CloudFormationResourceSummary],
        selected_resource_names: Set[str],
    ) -> List[CloudFormationResourceSummary]:
        """
        Returns list of resources which matches with selected_resource_names.
        selected_resource_names can be;
        - resource name like HelloWorldFunction
        - or it could be pointing to a resource in nested stack like NestedApp/HelloWorldFunction

        Parameters
        ----------
        resource_summaries : Dict[str, CloudFormationResourceSummary]
            Dictionary of resource key and CloudformationResourceSummary which was returned from given stack
        selected_resource_names : Set[str]
            List of resource name definitions that will be used to filter the results

        Returns
        ------
        List[CloudFormationResourceSummary]
            Filtered list of CloudFormationResourceSummary's
        """
        resources = []
        for selected_resource_name in selected_resource_names:
            selected_resource = resource_summaries.get(selected_resource_name)
            if selected_resource:
                resources.append(selected_resource)
            else:
                LOG.warning(
                    "Resource name (%s) does not exist. Available resource names: %s",
                    selected_resource_name,
                    ", ".join(resource_summaries.keys()),
                )
        return resources
