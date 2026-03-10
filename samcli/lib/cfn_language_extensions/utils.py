"""
Utility functions for CloudFormation Language Extensions.

This module provides shared helpers used across the SAM CLI codebase
for working with templates that may contain Fn::ForEach blocks.
"""

from typing import Dict, Iterator, Tuple

FOREACH_PREFIX = "Fn::ForEach::"

# Fn::ForEach structure requires exactly 3 elements: [loop_variable, collection, output_template]
FOREACH_REQUIRED_ELEMENTS = 3

# Set of AWS pseudo-parameter names
PSEUDO_PARAMETERS = {
    "AWS::AccountId",
    "AWS::NotificationARNs",
    "AWS::NoValue",
    "AWS::Partition",
    "AWS::Region",
    "AWS::StackId",
    "AWS::StackName",
    "AWS::URLSuffix",
}


def derive_partition(region: str) -> str:
    """Derive the AWS partition from the region."""
    if region.startswith("cn-"):
        return "aws-cn"
    elif region.startswith("us-gov-"):
        return "aws-us-gov"
    else:
        return "aws"


def derive_url_suffix(region: str) -> str:
    """Derive the AWS URL suffix from the region."""
    if region.startswith("cn-"):
        return "amazonaws.com.cn"
    else:
        return "amazonaws.com"


def is_foreach_key(key: str) -> bool:
    """Check if a resource key is a Fn::ForEach block."""
    return isinstance(key, str) and key.startswith(FOREACH_PREFIX)


def iter_regular_resources(template_dict: Dict) -> Iterator[Tuple[str, Dict]]:
    """
    Yield (logical_id, resource_dict) pairs from a template's Resources section,
    skipping Fn::ForEach blocks and non-dict entries.

    Parameters
    ----------
    template_dict : dict
        A CloudFormation template dictionary (must have a "Resources" key).

    Yields
    ------
    Tuple[str, dict]
        (logical_id, resource_dict) for each regular (non-ForEach) resource.
    """
    for key, value in template_dict.get("Resources", {}).items():
        if not is_foreach_key(key) and isinstance(value, dict):
            yield key, value
