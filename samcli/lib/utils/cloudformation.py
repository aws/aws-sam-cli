"""
This utility file contains methods to read information from certain CFN stack
"""
import logging
from typing import List, Dict, NamedTuple, Set, Optional

from botocore.exceptions import ClientError

from samcli.lib.utils.boto_utils import BotoProviderType

LOG = logging.getLogger(__name__)


class CloudFormationResourceSummary(NamedTuple):
    """
    Keeps information about CFN resource
    """

    resource_type: str
    logical_resource_id: str
    physical_resource_id: str


def get_physical_id_mapping(
    boto_resource_provider: BotoProviderType, stack_name: str, resource_types: Optional[Set[str]] = None
) -> Dict[str, str]:
    """
    Uses get_resource_summaries method to gather resource summaries and creates a dictionary which contains
    logical_id to physical_id mapping

    Parameters
    ----------
    boto_resource_provider : BotoProviderType
        A callable which will return boto3 resource
    stack_name : str
        Name of the stack which is deployed to CFN
    resource_types : Optional[Set[str]]
        List of resource types, which will filter the results

    Returns
    -------
        Dictionary of string, string which will contain logical_id to physical_id mapping

    """
    resource_summaries = get_resource_summaries(boto_resource_provider, stack_name, resource_types)

    resource_physical_id_map: Dict[str, str] = {}
    for resource_summary in resource_summaries:
        resource_physical_id_map[resource_summary.logical_resource_id] = resource_summary.physical_resource_id

    return resource_physical_id_map


def get_resource_summaries(
    boto_resource_provider: BotoProviderType, stack_name: str, resource_types: Optional[Set[str]] = None
) -> List[CloudFormationResourceSummary]:
    """
    Collects information about CFN resources and return their summary as list

    Parameters
    ----------
    boto_resource_provider : BotoProviderType
        A callable which will return boto3 resource
    stack_name : str
        Name of the stack which is deployed to CFN
    resource_types : Optional[Set[str]]
        List of resource types, which will filter the results

    Returns
    -------
        List of CloudFormationResourceSummary which contains information about resources in the given stack

    """
    LOG.debug("Fetching stack (%s) resources", stack_name)
    cfn_resource_summaries = boto_resource_provider("cloudformation").Stack(stack_name).resource_summaries.all()
    resource_summaries: List[CloudFormationResourceSummary] = []

    for cfn_resource_summary in cfn_resource_summaries:
        resource_summary = CloudFormationResourceSummary(
            cfn_resource_summary.resource_type,
            cfn_resource_summary.logical_resource_id,
            cfn_resource_summary.physical_resource_id,
        )
        if resource_types and resource_summary.resource_type not in resource_types:
            LOG.debug(
                "Skipping resource %s since its type %s is not supported. Supported types %s",
                resource_summary.logical_resource_id,
                resource_summary.resource_type,
                resource_types,
            )
            continue

        resource_summaries.append(resource_summary)

    return resource_summaries


def get_resource_summary(boto_resource_provider: BotoProviderType, stack_name: str, resource_logical_id: str):
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
