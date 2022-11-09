# pylint: disable=too-many-lines
"""
Terraform prepare hook implementation
"""
# pylint: disable=C0302
# TODO: Move some of the logic out of this file and remove this disable
from dataclasses import dataclass
import json
import os
from json.decoder import JSONDecodeError
from pathlib import Path
import re
from subprocess import run, CalledProcessError
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import hashlib
import logging
import shutil
import uuid

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import (
    _link_lambda_function_to_layer,
    _get_configuration_address,
    _build_module,
    _resolve_resource_attribute,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    ConstantValue,
    References,
    ResolvedReference,
    TFModule,
    TFResource,
)
from samcli.hook_packages.terraform.lib.utils import (
    build_cfn_logical_id,
    _calculate_configuration_attribute_value_hash,
    get_sam_metadata_planned_resource_value_attribute,
)
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.hook_packages.terraform.hooks.prepare.exceptions import InvalidSamMetadataPropertiesException
from samcli.lib.utils import osutils
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.utils.path_utils import convert_path_to_unix_path
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION as CFN_AWS_LAMBDA_LAYER_VERSION,
)
from samcli.lib.utils.subprocess_utils import invoke_subprocess_with_loading_pattern, LoadingPatternError

SAM_METADATA_DOCKER_TAG_ATTRIBUTE = "docker_tag"

SAM_METADATA_DOCKER_BUILD_ARGS_ATTRIBUTE = "docker_build_args"

SAM_METADATA_DOCKER_FILE_ATTRIBUTE = "docker_file"

SAM_METADATA_RESOURCE_TYPE_ATTRIBUTE = "resource_type"

SAM_METADATA_ADDRESS_ATTRIBUTE = "address"

SAM_METADATA_RESOURCE_NAME_ATTRIBUTE = "resource_name"

REMOTE_DUMMY_VALUE = "<<REMOTE DUMMY VALUE - RAISE ERROR IF IT IS STILL THERE>>"

LOG = logging.getLogger(__name__)

# check for python 3, 3.7 or above
# regex: search for 'Python', whitespace, '3.', digits 7-9 or 2+ digits, any digit or '.' 0+ times
PYTHON_VERSION_REGEX = re.compile(r"Python\s*3.([7-9]|\d{2,})[\d.]*")

TF_AWS_LAMBDA_FUNCTION = "aws_lambda_function"
TF_AWS_LAMBDA_LAYER_VERSION = "aws_lambda_layer_version"
AWS_PROVIDER_NAME = "registry.terraform.io/hashicorp/aws"
NULL_RESOURCE_PROVIDER_NAME = "registry.terraform.io/hashicorp/null"
SAM_METADATA_RESOURCE_TYPE = "null_resource"
SAM_METADATA_NAME_PREFIX = "sam_metadata_"

PropertyBuilder = Callable[[dict, TFResource], Any]
PropertyBuilderMapping = Dict[str, PropertyBuilder]

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


@dataclass
class ResourceTranslator:
    cfn_name: str
    property_builder_mapping: PropertyBuilderMapping


@dataclass
class SamMetadataResource:
    current_module_address: Optional[str]
    resource: Dict
    config_resource: TFResource


def prepare(params: dict) -> dict:
    """
    Prepares a terraform application for use with the SAM CLI

    Parameters
    ----------
    params: dict
        Parameters of the IaC application

    Returns
    -------
    dict
        information of the generated metadata files
    """
    output_dir_path = params.get("OutputDirPath")

    terraform_application_dir = params.get("IACProjectPath", os.getcwd())
    if not output_dir_path:
        raise PrepareHookException("OutputDirPath was not supplied")

    LOG.debug("Normalize the project root directory path %s", terraform_application_dir)
    if not os.path.isabs(terraform_application_dir):
        terraform_application_dir = os.path.normpath(os.path.join(os.getcwd(), terraform_application_dir))
        LOG.debug("The normalized project root directory path %s", terraform_application_dir)

    LOG.debug("Normalize the OutputDirPath %s", output_dir_path)
    if not os.path.isabs(output_dir_path):
        output_dir_path = os.path.normpath(os.path.join(terraform_application_dir, output_dir_path))
        LOG.debug("The normalized OutputDirPath value is %s", output_dir_path)

    skip_prepare_infra = params.get("SkipPrepareInfra")
    metadata_file_path = os.path.join(output_dir_path, TERRAFORM_METADATA_FILE)

    if skip_prepare_infra and os.path.exists(metadata_file_path):
        LOG.info("Skipping preparation stage, the metadata file already exists at %s", metadata_file_path)
    else:
        log_msg = (
            (
                "The option to skip infrastructure preparation was provided, but AWS SAM CLI could not find "
                f"the metadata file. Preparing anyways.{os.linesep}Initializing Terraform application"
            )
            if skip_prepare_infra
            else "Initializing Terraform application"
        )
        try:
            # initialize terraform application
            LOG.info(log_msg)
            invoke_subprocess_with_loading_pattern(
                command_args={
                    "args": ["terraform", "init", "-input=false"],
                    "cwd": terraform_application_dir,
                }
            )

            # get json output of terraform plan
            LOG.info("Creating terraform plan and getting JSON output")
            with osutils.tempfile_platform_independent() as temp_file:
                invoke_subprocess_with_loading_pattern(
                    # input false to avoid SAM CLI to stuck in case if the
                    # Terraform project expects input, and customer does not provide it.
                    command_args={
                        "args": ["terraform", "plan", "-out", temp_file.name, "-input=false"],
                        "cwd": terraform_application_dir,
                    }
                )

                result = run(
                    ["terraform", "show", "-json", temp_file.name],
                    check=True,
                    capture_output=True,
                    cwd=terraform_application_dir,
                )
            tf_json = json.loads(result.stdout)

            # convert terraform to cloudformation
            LOG.info("Generating metadata file")
            cfn_dict = _translate_to_cfn(tf_json, output_dir_path, terraform_application_dir)

            if cfn_dict.get("Resources"):
                _update_resources_paths(cfn_dict.get("Resources"), terraform_application_dir)  # type: ignore

            # Add hook metadata
            if not cfn_dict.get("Metadata"):
                cfn_dict["Metadata"] = {}
            cfn_dict["Metadata"][HOOK_METADATA_KEY] = TERRAFORM_HOOK_METADATA

            # store in supplied output dir
            if not os.path.exists(output_dir_path):
                os.makedirs(output_dir_path, exist_ok=True)

            LOG.info("Finished generating metadata file. Storing in %s", metadata_file_path)
            with open(metadata_file_path, "w+") as metadata_file:
                json.dump(cfn_dict, metadata_file)
        except CalledProcessError as e:
            stderr_output = str(e.stderr)

            # stderr can take on bytes or just be a plain string depending on terminal
            if isinstance(e.stderr, bytes):
                stderr_output = e.stderr.decode("utf-8")

            # one of the subprocess.run calls resulted in non-zero exit code or some OS error
            LOG.debug(
                "Error running terraform command: \n" "cmd: %s \n" "stdout: %s \n" "stderr: %s \n",
                e.cmd,
                e.stdout,
                stderr_output,
            )

            raise PrepareHookException(
                f"There was an error while preparing the Terraform application.\n{stderr_output}"
            ) from e
        except LoadingPatternError as e:
            raise PrepareHookException(f"Error occurred when invoking a process: {e}") from e
        except OSError as e:
            raise PrepareHookException(f"OSError: {e}") from e

    return {"iac_applications": {"MainApplication": {"metadata_file": metadata_file_path}}}


def _update_resources_paths(cfn_resources: Dict[str, Any], terraform_application_dir: str) -> None:
    """
    As Sam Cli and terraform handles the relative paths differently. Sam Cli handles the relative paths to be relative
    to the template, but terraform handles them to be relative to the project root directory. This Function purpose is
    to update the CFN resources paths to be absolute paths, and change relative paths to be relative to the terraform
    application root directory.

    Parameters
    ----------
    cfn_resources: dict
        CloudFormation resources
    terraform_application_dir: str
        The terraform application root directory where all paths will be relative to it
    """
    resources_attributes_to_be_updated = {
        resource_type: [property_value] for resource_type, property_value in CFN_CODE_PROPERTIES.items()
    }
    for _, resource in cfn_resources.items():
        if resource.get("Type") in resources_attributes_to_be_updated and isinstance(resource.get("Properties"), dict):
            for attribute in resources_attributes_to_be_updated[resource["Type"]]:
                original_path = resource.get("Properties", {}).get(attribute)
                if isinstance(original_path, str) and not os.path.isabs(original_path):
                    resource["Properties"][attribute] = str(Path(terraform_application_dir).joinpath(original_path))


def _translate_to_cfn(tf_json: dict, output_directory_path: str, terraform_application_dir: str) -> dict:
    """
    Translates the json output of a terraform show into CloudFormation

    Parameters
    ----------
    tf_json: dict
        A terraform show json output
    output_directory_path: str
        the string path to write the metadata file and makefile
    terraform_application_dir: str
        the terraform project root directory

    Returns
    -------
    dict
        The CloudFormation resulting from translating tf_json
    """
    # setup root_module and cfn dict
    root_module = tf_json.get("planned_values", {}).get("root_module")
    cfn_dict: dict = {"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}
    if not root_module:
        return cfn_dict

    LOG.debug("Mapping Lambda functions to their corresponding layers.")
    input_vars: Dict[str, Union[ConstantValue, References]] = {
        var_name: ConstantValue(value=var_value.get("value"))
        for var_name, var_value in tf_json.get("variables", {}).items()
    }
    root_tf_module = _build_module("", tf_json.get("configuration", {}).get("root_module"), input_vars, None)

    # to map s3 object sources to respective functions later
    # this dictionary will map between the hash value of the S3 Bucket attributes, and a tuple of the planned value
    # source code path, and the configuration value of the source code path.
    s3_hash_to_source: Dict[str, Tuple[str, List[Union[ConstantValue, ResolvedReference]]]] = {}

    # map code/imageuri to Lambda resources
    # the key is the hash value of lambda code/imageuri
    # the value is the list of pair of the resource logical id, and the lambda cfn resource dict
    lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]] = {}

    sam_metadata_resources: List[SamMetadataResource] = []

    lambda_layers_terraform_resources: Dict[str, Dict] = {}
    lambda_funcs_conf_cfn_resources: Dict[str, List] = {}
    lambda_config_funcs_conf_cfn_resources: Dict[str, TFResource] = {}

    # create and iterate over queue of modules to handle child modules
    module_queue = [(root_module, root_tf_module)]
    while module_queue:
        modules_pair = module_queue.pop(0)
        curr_module, curr_tf_module = modules_pair
        curr_module_address = curr_module.get("address")

        _add_child_modules_to_queue(curr_module, curr_tf_module, module_queue)

        # iterate over resources for current module
        resources = curr_module.get("resources", {})
        for resource in resources:
            resource_provider = resource.get("provider_name")
            resource_type = resource.get("type")
            resource_values = resource.get("values")
            resource_full_address = resource.get("address")
            resource_name = resource.get("name")
            resource_mode = resource.get("mode")

            resource_address = (
                f"data.{resource_type}.{resource_name}"
                if resource_mode == "data"
                else f"{resource_type}.{resource_name}"
            )
            config_resource_address = _get_configuration_address(resource_address)
            if config_resource_address not in curr_tf_module.resources:
                raise PrepareHookException(
                    f"There is no configuration resource for resource address {resource_full_address} and "
                    f"configuration address {config_resource_address}"
                )

            config_resource = curr_tf_module.resources[config_resource_address]

            if (
                resource_provider == NULL_RESOURCE_PROVIDER_NAME
                and resource_type == SAM_METADATA_RESOURCE_TYPE
                and resource_name.startswith(SAM_METADATA_NAME_PREFIX)
            ):
                _add_metadata_resource_to_metadata_list(
                    SamMetadataResource(curr_module_address, resource, config_resource),
                    resource,
                    sam_metadata_resources,
                )
                continue

            # only process supported provider
            if resource_provider != AWS_PROVIDER_NAME:
                continue

            # store S3 sources
            if resource_type == "aws_s3_object":
                s3_bucket = (
                    resource_values.get("bucket")
                    if "bucket" in resource_values
                    else _resolve_resource_attribute(config_resource, "bucket")
                )
                s3_key = (
                    resource_values.get("key")
                    if "key" in resource_values
                    else _resolve_resource_attribute(config_resource, "key")
                )
                obj_hash = _get_s3_object_hash(s3_bucket, s3_key)
                code_artifact = resource_values.get("source")
                config_code_artifact = (
                    code_artifact if code_artifact else _resolve_resource_attribute(config_resource, "source")
                )
                s3_hash_to_source[obj_hash] = (code_artifact, config_code_artifact)

            resource_translator = RESOURCE_TRANSLATOR_MAPPING.get(resource_type)
            # resource type not supported
            if not resource_translator:
                continue

            # translate TF resource "values" to CFN properties
            LOG.debug("Processing resource %s", resource_full_address)
            translated_properties = _translate_properties(
                resource_values, resource_translator.property_builder_mapping, config_resource
            )
            translated_resource = {
                "Type": resource_translator.cfn_name,
                "Properties": translated_properties,
                "Metadata": {"SamResourceId": resource_full_address, "SkipBuild": True},
            }

            # build CFN logical ID from resource address
            logical_id = build_cfn_logical_id(resource_full_address)

            # Add resource to cfn dict
            cfn_dict["Resources"][logical_id] = translated_resource

            if resource_type == TF_AWS_LAMBDA_LAYER_VERSION:
                lambda_layers_terraform_resources[logical_id] = resource
                planned_value_layer_code_path = translated_properties.get("Content")
                _add_lambda_resource_code_path_to_code_map(
                    config_resource,
                    "layer",
                    lambda_resources_to_code_map,
                    logical_id,
                    planned_value_layer_code_path,
                    "filename",
                    translated_resource,
                )

            if resource_type == TF_AWS_LAMBDA_FUNCTION:
                resolved_config_address = _get_configuration_address(resource_full_address)
                matched_lambdas = lambda_funcs_conf_cfn_resources.get(resolved_config_address, [])
                matched_lambdas.append(translated_resource)
                lambda_funcs_conf_cfn_resources[resolved_config_address] = matched_lambdas
                lambda_config_funcs_conf_cfn_resources[resolved_config_address] = config_resource

                resource_type = translated_properties.get("PackageType", ZIP)
                resource_type_constants = {ZIP: ("zip", "filename"), IMAGE: ("image", "image_uri")}
                planned_value_function_code_path = (
                    translated_properties.get("Code")
                    if resource_type == ZIP
                    else translated_properties.get("Code", {}).get("ImageUri")
                )
                func_type, tf_code_property = resource_type_constants[resource_type]

                _add_lambda_resource_code_path_to_code_map(
                    config_resource,
                    func_type,
                    lambda_resources_to_code_map,
                    logical_id,
                    planned_value_function_code_path,
                    tf_code_property,
                    translated_resource,
                )

    # map s3 object sources to corresponding functions
    LOG.debug("Mapping S3 object sources to corresponding functions")
    _map_s3_sources_to_functions(s3_hash_to_source, cfn_dict.get("Resources", {}), lambda_resources_to_code_map)

    _link_lambda_functions_to_layers(
        lambda_config_funcs_conf_cfn_resources, lambda_funcs_conf_cfn_resources, lambda_layers_terraform_resources
    )

    if sam_metadata_resources:
        LOG.debug("Enrich the mapped resources with the sam metadata information and generate Makefile")
        _enrich_resources_and_generate_makefile(
            sam_metadata_resources,
            cfn_dict.get("Resources", {}),
            output_directory_path,
            terraform_application_dir,
            lambda_resources_to_code_map,
        )
    else:
        LOG.debug("There is no sam metadata resources, no enrichment or Makefile is required")

    # check if there is still any dummy remote values for lambda resource imagesUri or S3 attributes
    _check_dummy_remote_values(cfn_dict.get("Resources", {}))

    return cfn_dict


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


def _add_metadata_resource_to_metadata_list(
    sam_metadata_resource: SamMetadataResource,
    sam_metadata_resource_planned_values: Dict,
    sam_metadata_resources: List[SamMetadataResource],
) -> None:
    """
    Prioritize the metadata resources that has resource name value to overwrite the metadata resources that does not
    have resource name value.

    Parameters
    ----------
    sam_metadata_resource: SamMetadataResource
        The mapped metadata resource
    sam_metadata_resource_planned_values: Dict
        The metadata resource in planned values section
    sam_metadata_resources: List[SamMetadataResource]
        The list of metadata resources
    """
    if get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource_planned_values, SAM_METADATA_RESOURCE_NAME_ATTRIBUTE
    ):
        sam_metadata_resources.append(sam_metadata_resource)
    else:
        sam_metadata_resources.insert(0, sam_metadata_resource)


def _add_child_modules_to_queue(curr_module: Dict, curr_module_configuration: TFModule, modules_queue: List) -> None:
    """
    Iterate over the children modules of current module and add each module with its related child module configuration
    to the modules_queue.

    Parameters
    ----------
    curr_module: Dict
        The current module in the planned values
    curr_module_configuration: TFModule
        The current module configuration
    modules_queue: List
        The list of modules
    """
    child_modules = curr_module.get("child_modules")
    if child_modules:
        for child_module in child_modules:
            config_child_module_address = (
                _get_configuration_address(child_module["address"]) if "address" in child_module else None
            )
            module_name = (
                config_child_module_address[config_child_module_address.rfind(".") + 1 :]
                if config_child_module_address
                else None
            )
            child_tf_module = curr_module_configuration.child_modules.get(module_name) if module_name else None
            if child_tf_module is None:
                raise PrepareHookException(
                    f"Module {config_child_module_address} exists in terraform planned_value, but does not exist "
                    "in terraform configuration"
                )
            modules_queue.append((child_module, child_tf_module))


def _link_lambda_functions_to_layers(
    lambda_config_funcs_conf_cfn_resources: Dict[str, TFResource],
    lambda_funcs_conf_cfn_resources: Dict[str, List],
    lambda_layers_terraform_resources: Dict[str, Dict],
):
    """
    Iterate through all of the resources and link the corresponding Lambda Layers to each Lambda Function

    Parameters
    ----------
    lambda_config_funcs_conf_cfn_resources: Dict[str, TFResource]
        Dictionary of configuration lambda resources
    lambda_funcs_conf_cfn_resources: Dict[str, List]
        Dictionary containing resolved configuration addresses matched up to the cfn Lambda functions
    lambda_layers_terraform_resources: Dict[str, Dict]
        Dictionary of all actual terraform layers resources (not configuration resources). The dictionary's key is the
        calculated logical id for each resource

    Returns
    -------
    dict
        The CloudFormation resulting from translating tf_json
    """
    for config_address, resource in lambda_config_funcs_conf_cfn_resources.items():
        if config_address in lambda_funcs_conf_cfn_resources:
            LOG.debug("Linking layers for Lambda function %s", resource.full_address)
            _link_lambda_function_to_layer(
                resource, lambda_funcs_conf_cfn_resources[config_address], lambda_layers_terraform_resources
            )


def _validate_referenced_resource_matches_sam_metadata_type(
    cfn_resource: dict, sam_metadata_resource: dict, sam_metadata_resource_address: str, expected_package_type: str
) -> None:
    """
    Validate if the resource that match the resource name provided in the sam metadata resource matches the resource
    type provided in the metadata as well.

    Parameters
    ----------
    cfn_resource: dict
        The CFN resource that matches the sam metadata resource name
    sam_metadata_resource: Dict
        The sam metadata resource properties
    sam_metadata_resource_address: str
        The sam metadata resource address
    expected_package_type: str
        The expected lambda function package type.
    """
    cfn_resource_properties = cfn_resource.get("Properties", {})
    resource_type = get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource, SAM_METADATA_RESOURCE_TYPE_ATTRIBUTE
    )
    cfn_resource_type = cfn_resource.get("Type")
    lambda_function_package_type = cfn_resource_properties.get("PackageType", ZIP)
    LOG.debug(
        "Validate if the referenced resource in sam metadata resource %s is of the expected type %s",
        sam_metadata_resource_address,
        resource_type,
    )

    if (
        cfn_resource_type != CFN_AWS_LAMBDA_FUNCTION
        or not cfn_resource_properties
        or lambda_function_package_type != expected_package_type
    ):
        LOG.error(
            "The matched resource is of type %s, and package type is %s, but the type mentioned in the sam metadata "
            "resource %s is %s",
            cfn_resource_type,
            lambda_function_package_type,
            sam_metadata_resource_address,
            resource_type,
        )
        raise InvalidSamMetadataPropertiesException(
            f"The sam metadata resource {sam_metadata_resource_address} is referring to a resource that does not "
            f"match the resource type {resource_type}."
        )


def _get_source_code_path(
    sam_metadata_resource: dict,
    sam_metadata_resource_address: str,
    project_root_dir: str,
    src_code_property_name: str,
    property_path_property_name: str,
    src_code_attribute_name: str,
) -> str:
    """
    Validate that sam metadata resource contains the valid metadata properties
    to get a lambda function or layer source code.

    Parameters
    ----------
    sam_metadata_resource: Dict
        The sam metadata resource properties
    sam_metadata_resource_address: str
        The sam metadata resource address
    project_root_dir: str
        the terraform project root directory path
    src_code_property_name: str
        the sam metadata property name that contains the lambda function or layer source code or docker context path
    property_path_property_name: str
        the sam metadata property name that contains the property to get the source code value if it was provided
        as json string
    src_code_attribute_name: str
        the lambda function or later source code or docker context to be used to raise the correct exception

    Returns
    -------
    str
        The lambda function or layer source code or docker context paths
    """
    LOG.debug(
        "Extract the %s from the sam metadata resource %s from property %s",
        src_code_attribute_name,
        sam_metadata_resource_address,
        src_code_property_name,
    )
    source_code = get_sam_metadata_planned_resource_value_attribute(sam_metadata_resource, src_code_property_name)
    source_code_property = get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource, property_path_property_name
    )
    LOG.debug(
        "The found %s value is %s and property value is %s", src_code_attribute_name, source_code, source_code_property
    )
    if not source_code:
        raise InvalidSamMetadataPropertiesException(
            f"The sam metadata resource {sam_metadata_resource_address} "
            f"should contain the lambda function/lambda layer "
            f"{src_code_attribute_name} in property {src_code_property_name}"
        )
    if isinstance(source_code, str):
        try:
            LOG.debug("Try to decode the %s value in case if it is a encoded JSON string.", src_code_attribute_name)
            source_code = json.loads(source_code)
            LOG.debug("The decoded value of the %s value is %s", src_code_attribute_name, source_code)
        except JSONDecodeError:
            LOG.debug("Source code value could not be parsed as a JSON object. Handle it as normal string value")

    if isinstance(source_code, dict):
        LOG.debug(
            "Process the extracted %s as JSON object using the property %s",
            src_code_attribute_name,
            source_code_property,
        )
        if not source_code_property:
            raise InvalidSamMetadataPropertiesException(
                f"The sam metadata resource {sam_metadata_resource_address} "
                f"should contain the lambda function/lambda layer "
                f"{src_code_attribute_name} property in property {property_path_property_name} as the "
                f"{src_code_property_name} value is an object"
            )
        cfn_source_code_path = source_code.get(source_code_property)
        if not cfn_source_code_path:
            LOG.error(
                "The property %s does not exist in the extracted %s JSON object %s",
                source_code_property,
                src_code_attribute_name,
                source_code,
            )
            raise InvalidSamMetadataPropertiesException(
                f"The sam metadata resource {sam_metadata_resource_address} "
                f"should contain a valid lambda function/lambda layer "
                f"{src_code_attribute_name} property in property {property_path_property_name} as the "
                f"{src_code_property_name} value is an object"
            )
    elif isinstance(source_code, list):
        # SAM CLI does not process multiple paths, so we will handle only the first value in this list
        LOG.debug(
            "Process the extracted %s as list, and get the first value as SAM CLI does not support multiple paths",
            src_code_attribute_name,
        )
        if len(source_code) < 1:
            raise InvalidSamMetadataPropertiesException(
                f"The sam metadata resource {sam_metadata_resource_address} "
                f"should contain the lambda function/lambda layer "
                f"{src_code_attribute_name} in property {src_code_property_name}, and it should not be an empty list"
            )
        cfn_source_code_path = source_code[0]
        if not cfn_source_code_path:
            raise InvalidSamMetadataPropertiesException(
                f"The sam metadata resource {sam_metadata_resource_address} "
                f"should contain a valid lambda/lambda layer function "
                f"{src_code_attribute_name} in property {src_code_property_name}"
            )
    else:
        cfn_source_code_path = source_code

    LOG.debug("The %s path value is %s", src_code_attribute_name, cfn_source_code_path)

    if not os.path.isabs(cfn_source_code_path):
        LOG.debug(
            "The %s path value is not absoulte value. Get the absolute value based on the root directory %s",
            src_code_attribute_name,
            project_root_dir,
        )
        cfn_source_code_path = os.path.normpath(os.path.join(project_root_dir, cfn_source_code_path))
        LOG.debug("The calculated absolute path of %s is %s", src_code_attribute_name, cfn_source_code_path)

    if not isinstance(cfn_source_code_path, str) or not os.path.exists(cfn_source_code_path):
        LOG.error("The path %s does not exist", cfn_source_code_path)
        raise InvalidSamMetadataPropertiesException(
            f"The sam metadata resource {sam_metadata_resource_address} should contain a valid string value for the "
            f"lambda function/lambda layer {src_code_attribute_name} path"
        )

    return cfn_source_code_path


def _enrich_zip_lambda_function(
    sam_metadata_resource: Dict,
    cfn_lambda_function: Dict,
    cfn_lambda_function_logical_id: str,
    terraform_application_dir: str,
    output_directory_path: str,
):
    """
    Use the sam metadata resources to enrich the zip lambda function.

    Parameters
    ----------
    sam_metadata_resource: Dict
        The sam metadata resource properties
    cfn_lambda_function: dict
        CloudFormation lambda function to be enriched
    cfn_lambda_function_logical_id: str
        the cloudFormation lambda function to be enriched logical id.
    output_directory_path: str
        the output directory path to write the generated metadata and makefile
    terraform_application_dir: str
        the terraform project root directory
    """
    sam_metadata_resource_address = sam_metadata_resource.get("address")
    if not sam_metadata_resource_address:
        raise PrepareHookException(
            "Invalid Terraform plan output. The address property should not be null to any terraform resource."
        )

    LOG.debug(
        "Enrich the ZIP lambda function %s using the metadata properties defined in resource %s",
        cfn_lambda_function_logical_id,
        sam_metadata_resource_address,
    )

    _validate_referenced_resource_matches_sam_metadata_type(
        cfn_lambda_function, sam_metadata_resource, sam_metadata_resource_address, ZIP
    )

    cfn_source_code_path = _get_source_code_path(
        sam_metadata_resource,
        sam_metadata_resource_address,
        terraform_application_dir,
        "original_source_code",
        "source_code_property",
        "source code",
    )
    _set_zip_metadata_resources(
        cfn_lambda_function,
        cfn_source_code_path,
        output_directory_path,
        terraform_application_dir,
        CFN_CODE_PROPERTIES[CFN_AWS_LAMBDA_FUNCTION],
    )


def _enrich_image_lambda_function(
    sam_metadata_resource: Dict,
    cfn_lambda_function: Dict,
    cfn_lambda_function_logical_id: str,
    terraform_application_dir: str,
    output_directory_path: str,
):
    """
    Use the sam metadata resources to enrich the image lambda function.

    Parameters
    ----------
    sam_metadata_resource: Dict
        The sam metadata resource properties
    cfn_lambda_function: dict
        CloudFormation lambda function to be enriched
    cfn_lambda_function_logical_id: str
        the cloudFormation lambda function to be enriched logical id.
    output_directory_path: str
        the output directory path to write the generated metadata and makefile
    terraform_application_dir: str
        the terraform project root directory
    """
    sam_metadata_resource_address = sam_metadata_resource.get("address")
    if not sam_metadata_resource_address:
        raise PrepareHookException(
            "Invalid Terraform plan output. The address property should not be null to any terraform resource."
        )
    cfn_resource_properties = cfn_lambda_function.get("Properties", {})

    LOG.debug(
        "Enrich the IMAGE lambda function %s using the metadata properties defined in resource %s",
        cfn_lambda_function_logical_id,
        sam_metadata_resource_address,
    )

    _validate_referenced_resource_matches_sam_metadata_type(
        cfn_lambda_function, sam_metadata_resource, sam_metadata_resource_address, IMAGE
    )

    cfn_docker_context_path = _get_source_code_path(
        sam_metadata_resource,
        sam_metadata_resource_address,
        terraform_application_dir,
        "docker_context",
        "docker_context_property_path",
        "docker context",
    )
    cfn_docker_file = get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource, SAM_METADATA_DOCKER_FILE_ATTRIBUTE
    )
    cfn_docker_build_args_string = get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource, SAM_METADATA_DOCKER_BUILD_ARGS_ATTRIBUTE
    )
    cfn_docker_build_args = None
    if cfn_docker_build_args_string:
        try:
            LOG.debug("Parse the docker build args %s", cfn_docker_build_args_string)
            cfn_docker_build_args = json.loads(cfn_docker_build_args_string)
            if not isinstance(cfn_docker_build_args, dict):
                raise InvalidSamMetadataPropertiesException(
                    f"The sam metadata resource {sam_metadata_resource_address} should contain a valid json "
                    f"encoded string for the lambda function docker build arguments."
                )
        except JSONDecodeError as exc:
            raise InvalidSamMetadataPropertiesException(
                f"The sam metadata resource {sam_metadata_resource_address} should contain a valid json encoded "
                f"string for the lambda function docker build arguments."
            ) from exc

    cfn_docker_tag = get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource, SAM_METADATA_DOCKER_TAG_ATTRIBUTE
    )

    if cfn_resource_properties.get("Code"):
        cfn_resource_properties.pop("Code")

    if not cfn_lambda_function.get("Metadata", {}):
        cfn_lambda_function["Metadata"] = {}
    cfn_lambda_function["Metadata"]["SkipBuild"] = False
    cfn_lambda_function["Metadata"]["DockerContext"] = cfn_docker_context_path
    if cfn_docker_file:
        cfn_lambda_function["Metadata"]["Dockerfile"] = cfn_docker_file
    if cfn_docker_tag:
        cfn_lambda_function["Metadata"]["DockerTag"] = cfn_docker_tag
    if cfn_docker_build_args:
        cfn_lambda_function["Metadata"]["DockerBuildArgs"] = cfn_docker_build_args


def _enrich_lambda_layer(
    sam_metadata_resource: Dict,
    cfn_lambda_layer: Dict,
    cfn_lambda_layer_logical_id: str,
    terraform_application_dir: str,
    output_directory_path: str,
) -> None:
    """
    Use the sam metadata resources to enrich the lambda layer.

    Parameters
    ----------
    sam_metadata_resource: Dict
       The sam metadata resource properties
    cfn_lambda_layer: dict
       CloudFormation lambda layer to be enriched
    cfn_lambda_layer_logical_id: str
       the cloudFormation lambda layer to be enriched logical id.
    output_directory_path: str
       the output directory path to write the generated metadata and makefile
    terraform_application_dir: str
       the terraform project root directory
    """
    sam_metadata_resource_address = sam_metadata_resource.get("address")
    if not sam_metadata_resource_address:
        raise PrepareHookException(
            "Invalid Terraform plan output. The address property should not be null to any terraform resource."
        )
    _validate_referenced_resource_layer_matches_metadata_type(
        cfn_lambda_layer, sam_metadata_resource, sam_metadata_resource_address
    )
    LOG.debug(
        "Enrich the Lambda Layer Version %s using the metadata properties defined in resource %s",
        cfn_lambda_layer_logical_id,
        sam_metadata_resource_address,
    )

    cfn_source_code_path = _get_source_code_path(
        sam_metadata_resource,
        sam_metadata_resource_address,
        terraform_application_dir,
        "original_source_code",
        "source_code_property",
        "source code",
    )

    _set_zip_metadata_resources(
        cfn_lambda_layer,
        cfn_source_code_path,
        output_directory_path,
        terraform_application_dir,
        CFN_CODE_PROPERTIES[CFN_AWS_LAMBDA_LAYER_VERSION],
    )


def _validate_referenced_resource_layer_matches_metadata_type(
    cfn_resource: dict,
    sam_metadata_resource: dict,
    sam_metadata_resource_address: str,
) -> None:
    """
    Validate if the resource that match the resource name provided in the sam metadata resource matches the resource
    type provided in the metadata as well.

    Parameters
    ----------
    cfn_resource: dict
        The CFN resource that matches the sam metadata resource name
    sam_metadata_resource: Dict
       The sam metadata resource properties
    sam_metadata_resource_address: str
        The sam metadata resource address
    """
    cfn_resource_properties = cfn_resource.get("Properties", {})
    resource_type = sam_metadata_resource.get(SAM_METADATA_RESOURCE_TYPE_ATTRIBUTE)
    cfn_resource_type = cfn_resource.get("Type")
    LOG.debug(
        "Validate if the referenced resource in sam metadata resource %s is of the expected type %s",
        sam_metadata_resource_address,
        resource_type,
    )

    if cfn_resource_type != CFN_AWS_LAMBDA_LAYER_VERSION or not cfn_resource_properties:
        LOG.error(
            "The matched resource is of type %s but the type mentioned in the sam metadata resource %s is %s",
            cfn_resource_type,
            sam_metadata_resource_address,
            resource_type,
        )
        raise InvalidSamMetadataPropertiesException(
            f"The sam metadata resource {sam_metadata_resource_address} is referring to a resource that does not "
            f"match the resource type {resource_type}."
        )


def _set_zip_metadata_resources(
    resource: dict,
    cfn_source_code_path: str,
    output_directory_path: str,
    terraform_application_dir: str,
    code_property: str,
) -> None:
    """
    Update the CloudFormation resource metadata with the enrichment properties from the TF resource

    Parameters
    ----------
    resource: dict
        The CFN resource that matches the sam metadata resource name
    cfn_source_code_path: dict
        Absolute path location of where the original source code resides.
    output_directory_path: str
        The directory where to find the Makefile the path to be copied into the temp dir.
    terraform_application_dir: str
        The working directory from which to run the Makefile.
    code_property:
        The property in the configuration used to denote the code e.g. "Code" or "Content"
    """
    resource_properties = resource.get("Properties", {})
    resource_properties[code_property] = cfn_source_code_path
    if not resource.get("Metadata", {}):
        resource["Metadata"] = {}
    resource["Metadata"]["SkipBuild"] = False
    resource["Metadata"]["BuildMethod"] = "makefile"
    resource["Metadata"]["ContextPath"] = output_directory_path
    resource["Metadata"]["WorkingDirectory"] = terraform_application_dir
    # currently we set the terraform project root directory that contains all the terraform artifacts as the project
    # directory till we work on the custom hook properties, and add a property for this value.
    resource["Metadata"]["ProjectRootDirectory"] = terraform_application_dir


def _enrich_resources_and_generate_makefile(
    sam_metadata_resources: List[SamMetadataResource],
    cfn_resources: Dict[str, Dict],
    output_directory_path: str,
    terraform_application_dir: str,
    lambda_resources_to_code_map: Dict,
) -> None:
    """
    Use the sam metadata resources to enrich the mapped resources and to create a Makefile with a rule for
    each lambda resource to be built.

    Parameters
    ----------
    sam_metadata_resources: List[SamMetadataResource]
        The list of sam metadata resources defined in the terraform project.
    cfn_resources: dict
        CloudFormation resources
    output_directory_path: str
        the output directory path to write the generated metadata and makefile
    terraform_application_dir: str
        the terraform project root directory
    lambda_resources_to_code_map: Dict
        The map between lambda resources code path, and lambda resources logical ids
    """

    python_command_name = _get_python_command_name()

    resources_types_enrichment_functions = {
        "ZIP_LAMBDA_FUNCTION": _enrich_zip_lambda_function,
        "IMAGE_LAMBDA_FUNCTION": _enrich_image_lambda_function,
        "LAMBDA_LAYER": _enrich_lambda_layer,
    }

    makefile_rules = []
    for sam_metadata_resource in sam_metadata_resources:
        # enrich resource
        resource_type = get_sam_metadata_planned_resource_value_attribute(
            sam_metadata_resource.resource, SAM_METADATA_RESOURCE_TYPE_ATTRIBUTE
        )
        sam_metadata_resource_address = sam_metadata_resource.resource.get("address")
        enrichment_function = resources_types_enrichment_functions.get(resource_type)
        if enrichment_function is None:
            raise InvalidSamMetadataPropertiesException(
                f"The resource type {resource_type} found in the sam metadata resource "
                f"{sam_metadata_resource_address} is not a correct resource type. The resource type should be one "
                f"of these values {resources_types_enrichment_functions.keys()}"
            )

        lambda_resources = _get_relevant_cfn_resource(
            sam_metadata_resource, cfn_resources, lambda_resources_to_code_map
        )
        for cfn_resource, logical_id in lambda_resources:
            enrichment_function(
                sam_metadata_resource.resource,
                cfn_resource,
                logical_id,
                terraform_application_dir,
                output_directory_path,
            )

            # get makefile rule for resource
            makefile_rule = _generate_makefile_rule_for_lambda_resource(
                sam_metadata_resource, logical_id, terraform_application_dir, python_command_name, output_directory_path
            )
            makefile_rules.append(makefile_rule)

    # generate makefile
    LOG.debug("Generate Makefile in %s", output_directory_path)
    _generate_makefile(makefile_rules, output_directory_path)


def _generate_makefile(
    makefile_rules: List[str],
    output_directory_path: str,
) -> None:
    """
    Generates a makefile with the given rules in the given directory
    Parameters
    ----------
    makefile_rules: List[str],
        the list of rules to write in the Makefile
    output_directory_path: str
        the output directory path to write the generated makefile
    """

    # create output directory if it doesn't exist
    if not os.path.exists(output_directory_path):
        os.makedirs(output_directory_path, exist_ok=True)

    # create z_samcli_backend_override.tf in output directory
    _generate_backend_override_file(output_directory_path)

    # copy copy_terraform_built_artifacts.py script into output directory
    copy_terraform_built_artifacts_script_path = os.path.join(
        Path(os.path.dirname(__file__)).parent.parent, TERRAFORM_BUILD_SCRIPT
    )
    shutil.copy(copy_terraform_built_artifacts_script_path, output_directory_path)

    # create makefile
    makefile_path = os.path.join(output_directory_path, "Makefile")
    with open(makefile_path, "w+") as makefile:
        makefile.writelines(makefile_rules)


def _generate_backend_override_file(output_directory_path: str):
    """
    Generates an override tf file to use a temporary backend

    Parameters
    ----------
    output_directory_path: str
        the output directory path to write the generated makefile
    """
    statefile_filename = f"{uuid.uuid4()}.tfstate"
    override_content = "terraform {\n" '  backend "local" {\n' f'    path = "./{statefile_filename}"\n' "  }\n" "}\n"
    override_file_path = os.path.join(output_directory_path, TF_BACKEND_OVERRIDE_FILENAME)
    with open(override_file_path, "w+") as f:
        f.write(override_content)


def _get_relevant_cfn_resource(
    sam_metadata_resource: SamMetadataResource,
    cfn_resources: Dict[str, Dict],
    lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]],
) -> List[Tuple[Dict, str]]:
    """
    use the sam metadata resource name property to determine the resource address, and transform the address to logical
    id to use it to get the cfn_resource.
    If the metadata resource does not contain a resource name property, so we need to use the resource built artifact
    path to find tha lambda resources that use the same artifact path

    Parameters
    ----------
    sam_metadata_resource: SamMetadataResource
        sam metadata resource that contain extra information about some resource.
    cfn_resources: Dict
        CloudFormation resources
    lambda_resources_to_code_map: Dict
        The map between lambda resources code path, and lambda resources logical ids

    Returns
    -------
    List[tuple(Dict, str)]
        The cfn resources that mentioned in the sam metadata resource, and the resource logical id
    """

    resources_types = {
        "ZIP_LAMBDA_FUNCTION": "zip",
        "IMAGE_LAMBDA_FUNCTION": "image",
        "LAMBDA_LAYER": "layer",
    }

    sam_metadata_resource_address = sam_metadata_resource.resource.get("address")
    resource_name = get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource.resource, SAM_METADATA_RESOURCE_NAME_ATTRIBUTE
    )
    resource_type = get_sam_metadata_planned_resource_value_attribute(
        sam_metadata_resource.resource, SAM_METADATA_RESOURCE_TYPE_ATTRIBUTE
    )
    if not resource_name:
        artifact_property_name = (
            "built_output_path" if resource_type in ["ZIP_LAMBDA_FUNCTION", "LAMBDA_LAYER"] else "built_image_uri"
        )
        artifact_path_value = get_sam_metadata_planned_resource_value_attribute(
            sam_metadata_resource.resource, artifact_property_name
        )
        if not artifact_path_value:
            artifact_path_value = _resolve_resource_attribute(
                sam_metadata_resource.config_resource, artifact_property_name
            )
        hash_value = (
            f"{resources_types[resource_type]}_{_calculate_configuration_attribute_value_hash(artifact_path_value)}"
        )
        lambda_resources = lambda_resources_to_code_map.get(hash_value, [])
        if not lambda_resources:
            raise InvalidSamMetadataPropertiesException(
                f"sam cli expects the sam metadata resource {sam_metadata_resource_address} to contain a resource name "
                f"that will be enriched using this metadata resource"
            )
        return lambda_resources
    # the provided resource name will be always a postfix to the module address. The customer could not set a full
    # address within a module.
    LOG.debug(
        "Check if the input resource name %s is a postfix to the current module address %s",
        resource_name,
        sam_metadata_resource.current_module_address,
    )
    full_resource_address = (
        f"{sam_metadata_resource.current_module_address}.{resource_name}"
        if sam_metadata_resource.current_module_address
        else resource_name
    )
    LOG.debug("check if the resource address %s has a relevant cfn resource or not", full_resource_address)
    logical_id = build_cfn_logical_id(full_resource_address)
    cfn_resource = cfn_resources.get(logical_id)
    if cfn_resource:
        LOG.debug("The CFN resource that match the input resource name %s is %s", resource_name, logical_id)
        return [(cfn_resource, logical_id)]

    raise InvalidSamMetadataPropertiesException(
        f"There is no resource found that match the provided resource name " f"{resource_name}"
    )


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


def _generate_makefile_rule_for_lambda_resource(
    sam_metadata_resource: SamMetadataResource,
    logical_id: str,
    terraform_application_dir: str,
    python_command_name: str,
    output_dir: str,
) -> str:
    """
    Generates and returns a makefile rule for the lambda resource associated with the given sam metadata resource.

    Parameters
    ----------
    sam_metadata_resource: SamMetadataResource
        A sam metadata resource; the generated makefile rule will correspond to building the lambda resource
        associated with this sam metadata resource
    logical_id: str
        Logical ID of the lambda resource
    terraform_application_dir: str
        the terraform project root directory
    python_command_name: str
        the python command name to use for running a script in the makefile rule
    output_dir: str
        the directory into which the Makefile is written

    Returns
    -------
    str
        The generated makefile rule
    """
    target = _get_makefile_build_target(logical_id)
    resource_address = sam_metadata_resource.resource.get("address", "")
    python_command_recipe = _format_makefile_recipe(
        _build_makerule_python_command(
            python_command_name, output_dir, resource_address, sam_metadata_resource, terraform_application_dir
        )
    )
    return f"{target}{python_command_recipe}"


def _build_makerule_python_command(
    python_command_name: str,
    output_dir: str,
    resource_address: str,
    sam_metadata_resource: SamMetadataResource,
    terraform_application_dir: str,
) -> str:
    """
    Build the Python command recipe to be used inside of the Makefile rule

    Parameters
    ----------
    python_command_name: str
        the python command name to use for running a script in the makefile recipe
    output_dir: str
        the directory into which the Makefile is written
    resource_address: str
        Address of a given terraform resource
    sam_metadata_resource: SamMetadataResource
        A sam metadata resource; the generated show command recipe will correspond to building the lambda resource
        associated with this sam metadata resource
    terraform_application_dir: str
        the terraform project root directory

    Returns
    -------
    str
        Fully resolved Terraform show command
    """
    show_command_template = (
        '{python_command_name} "{terraform_built_artifacts_script_path}" '
        '--expression "{jpath_string}" --directory "$(ARTIFACTS_DIR)" --target "{resource_address}"'
    )
    jpath_string = _build_jpath_string(sam_metadata_resource, resource_address)
    terraform_built_artifacts_script_path = convert_path_to_unix_path(
        str(Path(output_dir, TERRAFORM_BUILD_SCRIPT).relative_to(terraform_application_dir))
    )
    return show_command_template.format(
        python_command_name=python_command_name,
        terraform_built_artifacts_script_path=terraform_built_artifacts_script_path,
        jpath_string=jpath_string.replace('"', '\\"'),
        resource_address=resource_address.replace('"', '\\"'),
    )


def _build_jpath_string(sam_metadata_resource: SamMetadataResource, resource_address: str) -> str:
    """
    Constructs the JPath string for a given sam metadata resource from the planned_values
    to the build_output_path as is created by the Terraform plan output

    Parameters
    ----------
    sam_metadata_resource: SamMetadataResource
        A sam metadata resource; the generated recipe jpath will correspond to building the lambda resource
        associated with this sam metadata resource

    resource_address: str
        Full address of a Terraform resource

    Returns
    -------
    str
       Full JPath string for a resource from planned_values to build_output_path
    """
    jpath_string_template = (
        "|values|root_module{child_modules}|resources|"
        '[?address=="{resource_address}"]|values|triggers|built_output_path'
    )
    child_modules_template = "|child_modules|[?address=={module_address}]"
    module_address = sam_metadata_resource.current_module_address
    full_module_path = ""
    parent_modules = _get_parent_modules(module_address)
    for module in parent_modules:
        full_module_path += child_modules_template.format(module_address=module)
    jpath_string = jpath_string_template.format(child_modules=full_module_path, resource_address=resource_address)
    return jpath_string


def _get_parent_modules(module_address: Optional[str]) -> List[str]:
    """
    Convert an a full Terraform resource address to a list of module
    addresses from the root module to the current module

    e.g. "module.level1_lambda.module.level2_lambda" as input will return
    ["module.level1_lambda", "module.level1_lambda.module.level2_lambda"]

    Parameters
    ----------
    module_address: str
       Full address of the Terraform module

    Returns
    -------
    List[str]
       List of module addresses starting from the root module to the current module
    """
    if not module_address:
        return []

    # Split the address on "." then combine it back with the "module" prefix for each module name
    modules = module_address.split(".")
    modules = [".".join(modules[i : i + 2]) for i in range(0, len(modules), 2)]

    if not modules:
        # The format of the address was somehow different than we expected from the
        # module.<name>.module.<child_module_name>
        return []

    # Prefix each nested module name with the previous
    previous_module = modules[0]
    full_path_modules = [previous_module]
    for module in modules[1:]:
        module = previous_module + "." + module
        previous_module = module
        full_path_modules.append(module)
    return full_path_modules


def _get_makefile_build_target(logical_id: str) -> str:
    """
    Formats the Makefile rule build target string as is needed by the Makefile

    Parameters
    ----------
    logical_id: str
       Logical ID of the resource to use for the Makefile rule target

    Returns
    -------
    str
        The formatted Makefile rule build target
    """
    return f"build-{logical_id}:\n"


def _format_makefile_recipe(rule_string: str) -> str:
    """
    Formats the Makefile rule string as is needed by the Makefile

    Parameters
    ----------
    rule_string: str
       Makefile rule string to be formatted

    Returns
    -------
    str
        The formatted target rule
    """
    return f"\t{rule_string}\n"


def _translate_properties(
    tf_properties: dict, property_builder_mapping: PropertyBuilderMapping, resource: TFResource
) -> dict:
    """
    Translates the properties of a terraform resource into the equivalent properties of a CloudFormation resource

    Parameters
    ----------
    tf_properties: dict
        The terraform properties to translate
    property_builder_mappping: PropertyBuilderMapping
        A mapping of the CloudFormation property name to a function for building that property
    resource: TFResource
        The terraform configuration resource that can be used to retrieve some attributes values if needed

    Returns
    -------
    dict
        The CloudFormation properties resulting from translating tf_properties
    """
    cfn_properties = {}
    for cfn_property_name, cfn_property_builder in property_builder_mapping.items():
        cfn_property_value = cfn_property_builder(tf_properties, resource)
        if cfn_property_value is not None:
            cfn_properties[cfn_property_name] = cfn_property_value
    return cfn_properties


def _get_property_extractor(property_name: str) -> PropertyBuilder:
    """
    Returns a PropertyBuilder function to extract the given property from a dict

    Parameters
    ----------
    property_name: str
        The name of the property to extract

    Returns
    -------
    PropertyBuilder
        function that takes in a dict and extracts the given property name from it
    """
    return lambda properties, _: properties.get(property_name)


def _build_lambda_function_environment_property(tf_properties: dict, resource: TFResource) -> Optional[dict]:
    """
    Builds the Environment property of a CloudFormation AWS Lambda Function out of the
    properties of the equivalent terraform resource

    Parameters
    ----------
    tf_properties: dict
        Properties of the terraform AWS Lambda function resource
    resource: TFResource
        Configuration terraform resource

    Returns
    -------
    dict
        The built Environment property of a CloudFormation AWS Lambda Function resource
    """
    environment = tf_properties.get("environment")
    if not environment:
        return None

    for env in environment:
        variables = env.get("variables")
        if variables:
            return {"Variables": variables}

    # no variables
    return None


def _build_code_property(tf_properties: dict, resource: TFResource) -> Any:
    """
    Builds the Code property of a CloudFormation AWS Lambda Function out of the
    properties of the equivalent terraform resource

    Parameters
    ----------
    tf_properties: dict
        Properties of the terraform AWS Lambda function resource
    resource: TFResource
        Configuration terraform resource

    Returns
    -------
    dict
        The built Code property of a CloudFormation AWS Lambda Function resource
    """
    filename = tf_properties.get("filename")
    if filename:
        return filename

    code = {}
    tf_cfn_prop_names = [
        ("s3_bucket", "S3Bucket"),
        ("s3_key", "S3Key"),
        ("image_uri", "ImageUri"),
        ("s3_object_version", "S3ObjectVersion"),
    ]
    for tf_prop_name, cfn_prop_name in tf_cfn_prop_names:
        tf_prop_value = tf_properties.get(tf_prop_name)
        if tf_prop_value is not None:
            code[cfn_prop_name] = tf_prop_value

    package_type = tf_properties.get("package_type", ZIP)

    # Get the S3 Bucket details from configuration in case if the customer is creating the S3 bucket in the tf project
    if package_type == ZIP and ("S3Bucket" not in code or "S3Key" not in code or "S3ObjectVersion" not in code):
        s3_bucket_tf_config_value = _resolve_resource_attribute(resource, "s3_bucket")
        s3_key_tf_config_value = _resolve_resource_attribute(resource, "s3_key")
        s3_object_version_tf_config_value = _resolve_resource_attribute(resource, "s3_object_version")
        if "S3Bucket" not in code and s3_bucket_tf_config_value:
            code["S3Bucket"] = REMOTE_DUMMY_VALUE
            code["S3Bucket_config_value"] = s3_bucket_tf_config_value
        if "S3Key" not in code and s3_key_tf_config_value:
            code["S3Key"] = REMOTE_DUMMY_VALUE
            code["S3Key_config_value"] = s3_key_tf_config_value
        if "S3ObjectVersion" not in code and s3_object_version_tf_config_value:
            code["S3ObjectVersion"] = REMOTE_DUMMY_VALUE
            code["S3ObjectVersion_config_value"] = s3_object_version_tf_config_value

    # Get the Image URI details from configuration in case if the customer is creating the ecr repo in the tf project
    if package_type == IMAGE and "ImageUri" not in code:
        image_uri_tf_config_value = _resolve_resource_attribute(resource, "image_uri")
        if image_uri_tf_config_value:
            code["ImageUri"] = REMOTE_DUMMY_VALUE

    return code


def _build_lambda_function_image_config_property(tf_properties: dict, resource: TFResource) -> Optional[dict]:
    """
    Builds the ImageConfig property of a CloudFormation AWS Lambda Function out of the
    properties of the equivalent terraform resource

    Parameters
    ----------
    tf_properties: dict
        Properties of the terraform AWS Lambda function resource
    resource: TFResource
        Configuration terraform resource

    Returns
    -------
    dict
        The built ImageConfig property of a CloudFormation AWS Lambda Function resource
    """
    image_config = tf_properties.get("image_config")
    if not image_config:
        return None

    _check_image_config_value(image_config)
    image_config = image_config[0]

    cfn_image_config = {}
    tf_cfn_prop_names = [
        ("command", "Command"),
        ("entry_point", "EntryPoint"),
        ("working_directory", "WorkingDirectory"),
    ]

    for tf_prop_name, cfn_prop_name in tf_cfn_prop_names:
        tf_prop_value = image_config.get(tf_prop_name)
        if tf_prop_value is not None:
            cfn_image_config[cfn_prop_name] = tf_prop_value

    return cfn_image_config


def _check_image_config_value(image_config: Any) -> bool:
    """
    validate if the image_config property value is as SAM CLI expects. If it is not valid, it will raise a
    PrepareHookException.

     Parameters
    ----------
    image_config: Any
        The aws_lambda resource's Image_config property value as read from the terraform plan output.

    Returns
    -------
    bool
        return True, if the image_config value as expects, and raise PrepareHookException if not as expected.
    """
    if not isinstance(image_config, list):
        raise PrepareHookException(
            f"AWS SAM CLI expects that the value of image_config of aws_lambda_function resource in "
            f"the terraform plan output to be of type list instead of {type(image_config)}"
        )
    if len(image_config) > 1:
        raise PrepareHookException(
            f"AWS SAM CLI expects that there is only one item in the  image_config property of "
            f"aws_lambda_function resource in the terraform plan output, but there are "
            f"{len(image_config)} items"
        )
    return True


AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "FunctionName": _get_property_extractor("function_name"),
    "Architectures": _get_property_extractor("architectures"),
    "Environment": _build_lambda_function_environment_property,
    "Code": _build_code_property,
    "Handler": _get_property_extractor("handler"),
    "PackageType": _get_property_extractor("package_type"),
    "Runtime": _get_property_extractor("runtime"),
    "Layers": _get_property_extractor("layers"),
    "Timeout": _get_property_extractor("timeout"),
    "ImageConfig": _build_lambda_function_image_config_property,
}

AWS_LAMBDA_LAYER_VERSION_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "LayerName": _get_property_extractor("layer_name"),
    "CompatibleRuntimes": _get_property_extractor("compatible_runtimes"),
    "CompatibleArchitectures": _get_property_extractor("compatible_architectures"),
    "Content": _build_code_property,
}

RESOURCE_TRANSLATOR_MAPPING: Dict[str, ResourceTranslator] = {
    TF_AWS_LAMBDA_FUNCTION: ResourceTranslator(CFN_AWS_LAMBDA_FUNCTION, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING),
    TF_AWS_LAMBDA_LAYER_VERSION: ResourceTranslator(
        CFN_AWS_LAMBDA_LAYER_VERSION, AWS_LAMBDA_LAYER_VERSION_PROPERTY_BUILDER_MAPPING
    ),
}


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


def _map_s3_sources_to_functions(
    s3_hash_to_source: Dict[str, Tuple[str, List[Union[ConstantValue, ResolvedReference]]]],
    cfn_resources: Dict[str, Any],
    lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]],
) -> None:
    """
    Maps the source property of terraform AWS S3 object resources into the the Code property of
    CloudFormation AWS Lambda Function resources, and append the hash value of the artifacts path to the lambda
    resources code map.

    Parameters
    ----------
    s3_hash_to_source: Dict[str, Tuple[str, List[Union[ConstantValue, ResolvedReference]]]]
        Mapping of S3 object hash to S3 object source and the S3 Object configuration source value
    cfn_resources: dict
        CloudFormation resources
    lambda_resources_to_code_map: Dict
        the map between lambda resources code path values, and the lambda resources logical ids
    """
    for resource_logical_id, resource in cfn_resources.items():
        resource_type = resource.get("Type")
        if resource_type in CFN_CODE_PROPERTIES:
            code_property = CFN_CODE_PROPERTIES[resource_type]

            code = resource.get("Properties").get(code_property)

            # mapping not possible if function doesn't have bucket and key
            if isinstance(code, str):
                continue

            bucket = code.get("S3Bucket_config_value") if "S3Bucket_config_value" in code else code.get("S3Bucket")
            key = code.get("S3Key_config_value") if "S3Key_config_value" in code else code.get("S3Key")

            if bucket and key:
                obj_hash = _get_s3_object_hash(bucket, key)
                source = s3_hash_to_source.get(obj_hash)
                if source:
                    if source[0]:
                        tf_address = resource.get("Metadata", {}).get("SamResourceId")
                        LOG.debug(
                            "Found S3 object resource with matching bucket and key for function %s."
                            " Setting function's Code property to the matching S3 object's source: %s",
                            tf_address,
                            source[0],
                        )
                        resource["Properties"][code_property] = source[0]

                    references = source[0] or source[1]
                    res_type = "zip" if resource_type == CFN_AWS_LAMBDA_FUNCTION else "layer"
                    if references:
                        hash_value = f"{res_type}_{_calculate_configuration_attribute_value_hash(references)}"
                        resources_list = lambda_resources_to_code_map.get(hash_value, [])
                        resources_list.append((resource, resource_logical_id))
                        lambda_resources_to_code_map[hash_value] = resources_list


def _check_dummy_remote_values(cfn_resources: Dict[str, Any]) -> None:
    """
    Check if there is any lambda function/layer that has a dummy remote value for its code.imageuri or
    code.s3 attributes, and raise a validation error for it.

    Parameters
    ----------
    cfn_resources: dict
        CloudFormation resources
    """
    for _, resource in cfn_resources.items():
        resource_type = resource.get("Type")
        if resource_type in CFN_CODE_PROPERTIES:
            code_property = CFN_CODE_PROPERTIES[resource_type]

            code = resource.get("Properties").get(code_property)

            # there is no code property, this is the expected behaviour in image package type functions
            if code is None:
                continue

            # its value is a path to a local source code
            if isinstance(code, str):
                continue

            bucket = code.get("S3Bucket")
            key = code.get("S3Key")
            image_uri = code.get("ImageUri")

            if (bucket and bucket == REMOTE_DUMMY_VALUE) or (key and key == REMOTE_DUMMY_VALUE):
                raise PrepareHookException(
                    f"Lambda resource {resource.get('Metadata', {}).get('SamResourceId')} is referring to an S3 bucket "
                    f"that is not created yet, and there is no sam metadata resource set for it to build its code "
                    f"locally"
                )

            if image_uri and image_uri == REMOTE_DUMMY_VALUE:
                raise PrepareHookException(
                    f"Lambda resource {resource.get('Metadata', {}).get('SamResourceId')} is referring to an image uri "
                    "that is not created yet, and there is no sam metadata resource set for it to build its image "
                    "locally."
                )
