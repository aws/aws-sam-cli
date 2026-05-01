"""
Template serialization functions for CloudFormation Language Extensions.
"""

import json
from typing import Any, Dict, Optional

import yaml


def serialize_to_json(
    template: Dict[str, Any],
    indent: Optional[int] = 2,
    sort_keys: bool = False,
) -> str:
    """Serialize a processed CloudFormation template to JSON format.

    Args:
        template: The processed CloudFormation template dictionary.
        indent: Number of spaces for indentation. Use None for compact output.
        sort_keys: Whether to sort dictionary keys alphabetically.

    Returns:
        A JSON string representation of the template.
    """
    return json.dumps(template, indent=indent, sort_keys=sort_keys, ensure_ascii=False)


class CloudFormationDumper(yaml.SafeDumper):
    """Custom YAML dumper that uses literal block style for multi-line strings."""

    pass


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Custom string representer that uses literal block style for multi-line strings."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


CloudFormationDumper.add_representer(str, _str_representer)


def serialize_to_yaml(
    template: Dict[str, Any],
    default_flow_style: bool = False,
    sort_keys: bool = False,
    width: int = 80,
) -> str:
    """Serialize a processed CloudFormation template to YAML format.

    Args:
        template: The processed CloudFormation template dictionary.
        default_flow_style: If True, use flow style (inline) for collections.
        sort_keys: Whether to sort dictionary keys alphabetically.
        width: Maximum line width before wrapping.

    Returns:
        A YAML string representation of the template.
    """
    return yaml.dump(
        template,
        Dumper=CloudFormationDumper,
        default_flow_style=default_flow_style,
        sort_keys=sort_keys,
        width=width,
        allow_unicode=True,
    )
