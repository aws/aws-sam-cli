"""
Utility functions for CloudFormation Language Extensions.

This module provides shared helpers used across the SAM CLI codebase
for working with templates that may contain Fn::ForEach blocks.
"""

from typing import Dict, Iterator, Tuple

FOREACH_PREFIX = "Fn::ForEach::"


def is_foreach_key(key: str) -> bool:
    """Check if a resource key is a Fn::ForEach block."""
    return isinstance(key, str) and key.startswith(FOREACH_PREFIX)


def iter_resources(template_dict: Dict) -> Iterator[Tuple[str, Dict]]:
    """
    Yield (logical_id, resource_dict) pairs from a template's Resources section,
    skipping Fn::ForEach blocks and non-dict entries.

    This helper eliminates the repeated guard clause pattern:
        if key.startswith("Fn::ForEach::") or not isinstance(value, dict):
            continue

    Parameters
    ----------
    template_dict : dict
        A CloudFormation template dictionary (must have a "Resources" key).

    Yields
    ------
    Tuple[str, dict]
        (logical_id, resource_dict) for each regular resource.
    """
    for key, value in template_dict.get("Resources", {}).items():
        if not is_foreach_key(key) and isinstance(value, dict):
            yield key, value
