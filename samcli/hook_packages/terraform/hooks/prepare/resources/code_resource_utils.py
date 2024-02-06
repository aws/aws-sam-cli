"""
Utilities module specific to code resources such as Lambda functions and Lambda layers
"""

from typing import Any, Dict

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import _resolve_resource_attribute
from samcli.hook_packages.terraform.hooks.prepare.types import TFResource
from samcli.hook_packages.terraform.lib.utils import _calculate_configuration_attribute_value_hash


def _add_lambda_resource_code_path_to_code_map(
    terraform_resource: TFResource,
    lambda_resource_prefix: str,
    lambda_resources_to_code_map: Dict,
    logical_id: str,
    lambda_resource_code_value: Any,
    terraform_code_property_name: str,
    translated_resource: Dict,
) -> None:
    """
    Calculate the hash value of  the lambda resource code path planned value or the configuration value and use it to
    map the lambda resource logical id to the source code path. This will be used later to map the metadata resource to
    the correct lambda resource.

    Parameters
    ----------
    terraform_resource: TFResource
        The mapped TF resource. This will be used to resolve the configuration value of the code attribute in the lambda
         resource
    lambda_resource_prefix: str
        a string prefix to be added to the hash value to differentiate between the different lambda resources types
    lambda_resources_to_code_map: dict
        the map between lambda resources code path values, and the lambda resources logical ids
    logical_id: str
        lambda resource logical id
    lambda_resource_code_value: Any
        The planned value of the lambda resource code path
    terraform_code_property_name: str
        The lambda resource code property name
    translated_resource: Dict
        The CFN translated lambda resource
    """
    if not lambda_resource_code_value or not isinstance(lambda_resource_code_value, str):
        lambda_resource_code_value = _resolve_resource_attribute(terraform_resource, terraform_code_property_name)
    if lambda_resource_code_value:
        hash_value = (
            f"{lambda_resource_prefix}_{_calculate_configuration_attribute_value_hash(lambda_resource_code_value)}"
        )
        functions_list = lambda_resources_to_code_map.get(hash_value, [])
        functions_list.append((translated_resource, logical_id))
        lambda_resources_to_code_map[hash_value] = functions_list
