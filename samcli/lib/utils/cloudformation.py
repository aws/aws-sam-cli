"""
This utility file contains methods to read information from certain CFN stack
"""
import logging
import posixpath
from typing import Dict, Set, Optional, Iterable, Any

from attr import dataclass
from botocore.exceptions import ClientError

from samcli.lib.utils.boto_utils import BotoProviderType, get_client_error_code
from samcli.lib.utils.resources import AWS_CLOUDFORMATION_STACK

LOG = logging.getLogger(__name__)


# list of possible values for active stacks
# CFN console has a way to display active stacks but it is not possible in API calls
STACK_ACTIVE_STATUS = [
    "CREATE_IN_PROGRESS",
    "CREATE_COMPLETE",
    "ROLLBACK_IN_PROGRESS",
    "ROLLBACK_FAILED",
    "ROLLBACK_COMPLETE",
    "DELETE_IN_PROGRESS",
    "DELETE_FAILED",
    "UPDATE_IN_PROGRESS",
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_COMPLETE",
    "UPDATE_ROLLBACK_IN_PROGRESS",
    "UPDATE_ROLLBACK_FAILED",
    "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_ROLLBACK_COMPLETE",
    "REVIEW_IN_PROGRESS",
]


@dataclass
class CloudFormationResourceSummary:
    """
    Keeps information about CFN resource
    """

    resource_type: str
    logical_resource_id: str
    physical_resource_id: str


def get_resource_summaries(
    boto_resource_provider: BotoProviderType,
    boto_client_provider: BotoProviderType,
    stack_name: str,
    resource_types: Optional[Set[str]] = None,
    nested_stack_prefix: Optional[str] = None,
) -> Dict[str, CloudFormationResourceSummary]:
    """
    Collects information about CFN resources and return their summary as list

    Parameters
    ----------
    boto_resource_provider : BotoProviderType
        A callable which will return boto3 resource
    boto_client_provider : BotoProviderType
        A callable which will return boto3 client
    stack_name : str
        Name of the stack which is deployed to CFN
    resource_types : Optional[Set[str]]
        List of resource types, which will filter the results
    nested_stack_prefix: Optional[str]
        This will contain logical id of the parent stack. So that ChildStackA/GrandChildStackB so that resources
        under GrandChildStackB can create their keys like ChildStackA/GrandChildStackB/MyFunction

    Returns
    -------
        List of CloudFormationResourceSummary which contains information about resources in the given stack

    """
    LOG.debug("Fetching stack (%s) resources", stack_name)
    try:
        cfn_resource_summaries = list(
            boto_resource_provider("cloudformation").Stack(stack_name).resource_summaries.all()
        )
    except ClientError as ex:
        if get_client_error_code(ex) == "ValidationError" and LOG.isEnabledFor(logging.DEBUG):
            LOG.debug(
                "Invalid stack name (%s). Available stack names: %s",
                stack_name,
                ", ".join(list_active_stack_names(boto_client_provider)),
            )
        raise ex
    resource_summaries: Dict[str, CloudFormationResourceSummary] = {}

    for cfn_resource_summary in cfn_resource_summaries:
        resource_summary = CloudFormationResourceSummary(
            cfn_resource_summary.resource_type,
            cfn_resource_summary.logical_resource_id,
            cfn_resource_summary.physical_resource_id,
        )
        if resource_summary.resource_type == AWS_CLOUDFORMATION_STACK:
            new_nested_stack_prefix = resource_summary.logical_resource_id
            if nested_stack_prefix:
                new_nested_stack_prefix = posixpath.join(nested_stack_prefix, new_nested_stack_prefix)
            resource_summaries.update(
                get_resource_summaries(
                    boto_resource_provider,
                    boto_client_provider,
                    resource_summary.physical_resource_id,
                    resource_types,
                    new_nested_stack_prefix,
                )
            )
        if resource_types and resource_summary.resource_type not in resource_types:
            LOG.debug(
                "Skipping resource %s since its type %s is not supported. Supported types %s",
                resource_summary.logical_resource_id,
                resource_summary.resource_type,
                resource_types,
            )
            continue

        resource_key = resource_summary.logical_resource_id
        if nested_stack_prefix:
            resource_key = posixpath.join(nested_stack_prefix, resource_key)
        resource_summaries[resource_key] = resource_summary

    return resource_summaries


def get_resource_summary(
    boto_resource_provider: BotoProviderType, stack_name: str, resource_logical_id: str
) -> Optional[CloudFormationResourceSummary]:
    """
    Returns resource summary of given single resource with its logical id

    Parameters
    ----------
    boto_resource_provider : BotoProviderType
        A callable which will return boto3 resource
    stack_name : str
        Name of the stack which is deployed to CFN
    resource_logical_id : str
        Logical ID of the resource that will be returned as resource summary

    Returns
    -------
        CloudFormationResourceSummary of the resource which is identified by given logical id
    """
    try:
        cfn_resource_summary = boto_resource_provider("cloudformation").StackResource(stack_name, resource_logical_id)

        return CloudFormationResourceSummary(
            cfn_resource_summary.resource_type,
            cfn_resource_summary.logical_resource_id,
            cfn_resource_summary.physical_resource_id,
        )
    except ClientError as e:
        LOG.error(
            "Failed to pull resource (%s) information from stack (%s)", resource_logical_id, stack_name, exc_info=e
        )
        return None


def list_active_stack_names(boto_client_provider: BotoProviderType, show_nested_stacks: bool = False) -> Iterable[str]:
    """
    Returns list of active cloudformation stack names

    Parameters
    ----------
    boto_client_provider : BotoProviderType
        A callable which will return boto3 client
    show_nested_stacks : bool
        True; will display nested stack names as well. False; will hide nested stack names from the list.

    Returns
    -------
        Iterable[str] List of stack names that is currently active
    """
    cfn_client = boto_client_provider("cloudformation")
    first_call = True
    next_token: Optional[str] = None

    while first_call or next_token:
        first_call = False
        kwargs: Dict[str, Any] = {"StackStatusFilter": STACK_ACTIVE_STATUS}
        if next_token:
            kwargs["NextToken"] = next_token
        list_stacks_result = cfn_client.list_stacks(**kwargs)
        for stack_summary in list_stacks_result.get("StackSummaries", []):
            if not show_nested_stacks and stack_summary.get("RootId"):
                continue
            yield stack_summary.get("StackName")
        next_token = list_stacks_result.get("NextToken")
