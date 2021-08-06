"""
Read and parse CLI args for the Logs Command and setup the context for running the command
"""

import logging
from typing import List, Optional, Set, Any

from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION,
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)
from samcli.commands.exceptions import UserException
from samcli.lib.utils.boto_utils import BotoProviderType
from samcli.lib.utils.cloudformation import get_resource_summaries
from samcli.lib.utils.time import to_utc, parse_date

LOG = logging.getLogger(__name__)


class InvalidTimestampError(UserException):
    """
    Used to indicate that given date time string is an invalid timestamp
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
    if not time_str:
        return None

    parsed = parse_date(time_str)
    if not parsed:
        raise InvalidTimestampError("Unable to parse the time provided by '{}'".format(property_name))

    return to_utc(parsed)


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
        stack_name: str,
        resource_names: Optional[List[str]] = None,
        supported_resource_types: Optional[Set[str]] = None,
    ):
        self._boto_resource_provider = boto_resource_provider
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

    def _fetch_resources_from_stack(self, selected_resource_names: Optional[Set[str]] = None) -> List[Any]:
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
        List[StackResourceSummary]
            List of resource information, which will be used to fetch the logs
        """
        results = []
        LOG.debug("Getting logical id of the all resources for stack '%s'", self._stack_name)
        stack_resources = get_resource_summaries(
            self._boto_resource_provider, self._stack_name, ResourcePhysicalIdResolver.DEFAULT_SUPPORTED_RESOURCES
        )

        if selected_resource_names is None:
            selected_resource_names = {stack_resource.logical_resource_id for stack_resource in stack_resources}

        for resource in stack_resources:
            # if resource name is not selected, continue
            if resource.logical_resource_id not in selected_resource_names:
                LOG.debug("Resource (%s) is not selected with given input", resource.logical_resource_id)
                continue
            results.append(resource)
        return results
