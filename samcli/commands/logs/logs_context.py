"""
Read and parse CLI args for the Logs Command and setup the context for running the command
"""

import logging
from typing import List, Optional, Set, Any

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION
from samcli.commands.exceptions import UserException
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
    DEFAULT_SUPPORTED_RESOURCES: Set[str] = {AWS_LAMBDA_FUNCTION}

    def __init__(
        self,
        cfn_resource: Any,
        stack_name: str,
        resource_names: Optional[List[str]] = None,
        supported_resource_types: Optional[Set[str]] = None,
    ):
        self._cfn_resource = cfn_resource
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
        stack_resources = self._get_stack_resources()

        if selected_resource_names is None:
            selected_resource_names = {stack_resource.logical_id for stack_resource in stack_resources}

        for resource in stack_resources:
            # if resource name is not selected, continue
            if resource.logical_id not in selected_resource_names:
                LOG.debug("Resource (%s) is not selected with given input", resource.logical_id)
                continue
            # if resource type is not supported, continue
            if not self.is_supported_resource(resource.resource_type):
                LOG.debug(
                    "Resource (%s) with type (%s) is not supported, skipping",
                    resource.logical_id,
                    resource.resource_type,
                )
                continue
            results.append(resource)
        return results

    def _get_stack_resources(self) -> Any:
        """
        Fetches all resource information for the given stack, response is type of StackResourceSummariesCollection
        """
        cfn_stack = self._cfn_resource.Stack(self._stack_name)
        return cfn_stack.resource_summaries.all()

    def is_supported_resource(self, resource_type: str) -> bool:
        return resource_type in self._supported_resource_types
