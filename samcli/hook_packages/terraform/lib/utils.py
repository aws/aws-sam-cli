"""Terraform utilities"""

import hashlib
from typing import Any, Dict, List, Union

from samcli.hook_packages.terraform.hooks.prepare.types import (
    ConstantValue,
    ResolvedReference,
)
from samcli.lib.utils.hash import str_checksum

# max logical id len is 255
LOGICAL_ID_HASH_LEN = 8
LOGICAL_ID_MAX_HUMAN_LEN = 247


def build_cfn_logical_id(tf_address: str) -> str:
    """
    Builds a CloudFormation logical ID out of a terraform resource address

    Parameters
    ----------
    tf_address: str
        terraform resource address

    Returns
    -------
    str
        CloudFormation logical ID
    """
    # ignores non-alphanumericals, makes uppercase the first alphanumerical char and the
    # alphanumerical char right after a non-alphanumerical char
    chars: List[str] = []
    nextCharUppercase = True
    for char in tf_address:
        if len(chars) == LOGICAL_ID_MAX_HUMAN_LEN:
            break
        if not char.isalnum():
            nextCharUppercase = True
            continue
        if nextCharUppercase:
            chars.append(char.upper())
            nextCharUppercase = False
        else:
            chars.append(char)

    # Add a hash to avoid naming conflicts
    human_part = "".join(chars)
    hash_part = str_checksum(tf_address)[:LOGICAL_ID_HASH_LEN].upper()

    return human_part + hash_part


def _calculate_configuration_attribute_value_hash(
    configuration_attribute_value: Union[str, List[Union[ConstantValue, ResolvedReference]]]
) -> str:
    """
    Create a hash value of an attribute value of the resource configuration.

    Parameters
    ----------
    configuration_attribute_value: Union[str, List[Union[ConstantValue, ResolvedReference]]]
        An attribute value of the resource configuration. Its value can be either string if it can be resolved from
        the planned value section, or a list of references to other attributes.

    Returns
    -------
    str
        hash for the given object
    """
    md5 = hashlib.md5()

    if isinstance(configuration_attribute_value, str):
        md5.update(configuration_attribute_value.encode())
    else:
        sorted_references_list = sorted(
            configuration_attribute_value,
            key=lambda x: x.value if isinstance(x, ConstantValue) else f"{x.module_address}.{x.value}",
        )
        for ref in sorted_references_list:
            md5.update(
                ref.value.encode() if isinstance(ref, ConstantValue) else f"{ref.module_address}.{ref.value}".encode()
            )
    return md5.hexdigest()


def get_sam_metadata_planned_resource_value_attribute(
    sam_metadata_resource_planned_values: Dict, attr_name: str
) -> Any:
    return sam_metadata_resource_planned_values.get("values", {}).get("triggers", {}).get(attr_name)
