"""
Template serialization functions for CloudFormation Language Extensions.

This module provides functions to serialize processed CloudFormation templates
to JSON and YAML formats. The serialization functions produce valid output
that can be parsed by standard JSON and YAML parsers.

Requirements:
    - 13.1: THE Package SHALL provide a function to serialize processed templates to JSON format
    - 13.2: THE Package SHALL provide a function to serialize processed templates to YAML format
    - 13.3: JSON serialization SHALL produce valid JSON that can be parsed back
    - 13.4: YAML serialization SHALL produce valid YAML that can be parsed back
"""

import json
from typing import Any, Dict, Optional

import yaml


def serialize_to_json(
    template: Dict[str, Any],
    indent: Optional[int] = 2,
    sort_keys: bool = False,
) -> str:
    """
    Serialize a processed CloudFormation template to JSON format.

    This function produces valid JSON that can be parsed by standard JSON parsers.
    The output is suitable for use with CloudFormation or other tools that
    consume JSON templates.

    Args:
        template: The processed CloudFormation template dictionary.
        indent: Number of spaces for indentation. Use None for compact output.
                Defaults to 2 for readable output.
        sort_keys: Whether to sort dictionary keys alphabetically.
                   Defaults to False to preserve original key order.

    Returns:
        A JSON string representation of the template.

    Raises:
        TypeError: If the template contains non-JSON-serializable values.

    Example:
        >>> template = {"Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}}}
        >>> json_str = serialize_to_json(template)
        >>> print(json_str)
        {
          "Resources": {
            "MyQueue": {
              "Type": "AWS::SQS::Queue"
            }
          }
        }

    Requirements:
        - 13.1: Provide function to serialize to JSON format
        - 13.3: Produce valid JSON that can be parsed back
    """
    return json.dumps(template, indent=indent, sort_keys=sort_keys, ensure_ascii=False)


class CloudFormationDumper(yaml.SafeDumper):
    """
    Custom YAML dumper for CloudFormation templates.

    This dumper handles CloudFormation-specific YAML features:
    - Preserves multi-line strings using literal block scalar style (|)
    - Handles CloudFormation intrinsic function tags if present
    - Produces clean, readable YAML output
    """

    pass


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """
    Custom string representer that uses literal block style for multi-line strings.

    This makes the YAML output more readable for strings containing newlines,
    which is common in CloudFormation templates (e.g., inline code, policies).
    """
    if "\n" in data:
        # Use literal block scalar style for multi-line strings
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


# Register the custom string representer
CloudFormationDumper.add_representer(str, _str_representer)


def serialize_to_yaml(
    template: Dict[str, Any],
    default_flow_style: bool = False,
    sort_keys: bool = False,
    width: int = 80,
) -> str:
    """
    Serialize a processed CloudFormation template to YAML format.

    This function produces valid YAML that can be parsed by standard YAML parsers.
    The output is suitable for use with CloudFormation or other tools that
    consume YAML templates.

    The function handles CloudFormation-specific YAML features:
    - Multi-line strings are formatted using literal block scalar style (|)
    - Output is formatted for readability with proper indentation

    Args:
        template: The processed CloudFormation template dictionary.
        default_flow_style: If True, use flow style (inline) for collections.
                           If False (default), use block style for readability.
        sort_keys: Whether to sort dictionary keys alphabetically.
                   Defaults to False to preserve original key order.
        width: Maximum line width before wrapping. Defaults to 80.

    Returns:
        A YAML string representation of the template.

    Example:
        >>> template = {"Resources": {"MyQueue": {"Type": "AWS::SQS::Queue"}}}
        >>> yaml_str = serialize_to_yaml(template)
        >>> print(yaml_str)
        Resources:
          MyQueue:
            Type: AWS::SQS::Queue

    Requirements:
        - 13.2: Provide function to serialize to YAML format
        - 13.4: Produce valid YAML that can be parsed back
    """
    return yaml.dump(
        template,
        Dumper=CloudFormationDumper,
        default_flow_style=default_flow_style,
        sort_keys=sort_keys,
        width=width,
        allow_unicode=True,
    )
