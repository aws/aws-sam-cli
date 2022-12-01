"""Terraform utilities"""
import hashlib
import re
from typing import List, Union, Dict, Any
from subprocess import run, CalledProcessError

from samcli.lib.utils.hash import str_checksum
from samcli.hook_packages.terraform.hooks.prepare.types import (
    ConstantValue,
    ResolvedReference,
)
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION as CFN_AWS_LAMBDA_LAYER_VERSION,
)
from samcli.lib.hook.exceptions import PrepareHookException

# max logical id len is 255
LOGICAL_ID_HASH_LEN = 8
LOGICAL_ID_MAX_HUMAN_LEN = 247

SAM_METADATA_DOCKER_TAG_ATTRIBUTE = "docker_tag"
SAM_METADATA_DOCKER_BUILD_ARGS_ATTRIBUTE = "docker_build_args"
SAM_METADATA_DOCKER_FILE_ATTRIBUTE = "docker_file"
SAM_METADATA_RESOURCE_TYPE_ATTRIBUTE = "resource_type"
SAM_METADATA_RESOURCE_NAME_ATTRIBUTE = "resource_name"
SAM_METADATA_RESOURCE_TYPE = "null_resource"
SAM_METADATA_ADDRESS_ATTRIBUTE = "address"
SAM_METADATA_NAME_PREFIX = "sam_metadata_"

# check for python 3, 3.7 or above
# regex: search for 'Python', whitespace, '3.', digits 7-9 or 2+ digits, any digit or '.' 0+ times
PYTHON_VERSION_REGEX = re.compile(r"Python\s*3.([7-9]|\d{2,})[\d.]*")

AWS_PROVIDER_NAME = "registry.terraform.io/hashicorp/aws"
NULL_RESOURCE_PROVIDER_NAME = "registry.terraform.io/hashicorp/null"

TERRAFORM_METADATA_FILE = "template.json"
TERRAFORM_BUILD_SCRIPT = "copy_terraform_built_artifacts.py"
TF_BACKEND_OVERRIDE_FILENAME = "z_samcli_backend_override"

HOOK_METADATA_KEY = "AWS::SAM::Hook"
TERRAFORM_HOOK_METADATA = {
    "HookName": "terraform",
}

CFN_CODE_PROPERTIES = {
    CFN_AWS_LAMBDA_FUNCTION: "Code",
    CFN_AWS_LAMBDA_LAYER_VERSION: "Content",
}


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
            key=lambda x: x.value if isinstance(x, ConstantValue) else f"{x.module_address}.{x.value}",  # type: ignore
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


def _get_python_command_name() -> str:
    """
    Verify that python is installed and return the name of the python command

    Returns
    -------
    str
        The name of the python command installed
    """
    command_names_to_try = ["python3", "py3", "python", "py"]
    for command_name in command_names_to_try:
        try:
            run_result = run([command_name, "--version"], check=True, capture_output=True, text=True)
        except CalledProcessError:
            pass
        except OSError:
            pass
        else:
            # check python version
            if not PYTHON_VERSION_REGEX.match(run_result.stdout):
                continue
            return command_name
    raise PrepareHookException("Python not found. Please ensure that python 3.7 or above is installed.")


def _get_s3_object_hash(
    bucket: Union[str, List[Union[ConstantValue, ResolvedReference]]],
    key: Union[str, List[Union[ConstantValue, ResolvedReference]]],
) -> str:
    """
    Creates a hash for an AWS S3 object out of the bucket and key

    Parameters
    ----------
    bucket: Union[str, List[Union[ConstantValue, ResolvedReference]]]
        bucket for the S3 object
    key: Union[str, List[Union[ConstantValue, ResolvedReference]]]
        key for the S3 object

    Returns
    -------
    str
        hash for the given bucket and key
    """
    md5 = hashlib.md5()
    md5.update(_calculate_configuration_attribute_value_hash(bucket).encode())
    md5.update(_calculate_configuration_attribute_value_hash(key).encode())
    # TODO: Hash version if it exists in addition to key and bucket
    return md5.hexdigest()
