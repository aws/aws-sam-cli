"""
Terraform resource enrichment

This module populates the values required for each of the Lambda resources
"""
import json
import logging
import os
import re
from json.decoder import JSONDecodeError
from subprocess import CalledProcessError, run
from typing import Dict, List, Tuple

from samcli.hook_packages.terraform.hooks.prepare.constants import (
    CFN_CODE_PROPERTIES,
    SAM_METADATA_RESOURCE_NAME_ATTRIBUTE,
)
from samcli.hook_packages.terraform.hooks.prepare.exceptions import InvalidSamMetadataPropertiesException
from samcli.hook_packages.terraform.hooks.prepare.makefile_generator import (
    generate_makefile,
    generate_makefile_rule_for_lambda_resource,
)
from samcli.hook_packages.terraform.hooks.prepare.resource_linking import _resolve_resource_attribute
from samcli.hook_packages.terraform.hooks.prepare.types import SamMetadataResource
from samcli.hook_packages.terraform.lib.utils import (
    _calculate_configuration_attribute_value_hash,
    build_cfn_logical_id,
    get_sam_metadata_planned_resource_value_attribute,
)
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION
from samcli.lib.utils.resources import AWS_LAMBDA_LAYERVERSION as CFN_AWS_LAMBDA_LAYER_VERSION

SAM_METADATA_DOCKER_TAG_ATTRIBUTE = "docker_tag"
SAM_METADATA_DOCKER_BUILD_ARGS_ATTRIBUTE = "docker_build_args"
SAM_METADATA_DOCKER_FILE_ATTRIBUTE = "docker_file"
SAM_METADATA_RESOURCE_TYPE_ATTRIBUTE = "resource_type"

# check for python 3, 3.7 or above
# regex: search for 'Python', whitespace, '3.', digits 7-9 or 2+ digits, any digit or '.' 0+ times
PYTHON_VERSION_REGEX = re.compile(r"Python\s*3.([7-9]|\d{2,})[\d.]*")

LOG = logging.getLogger(__name__)


def enrich_resources_and_generate_makefile(
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
            makefile_rule = generate_makefile_rule_for_lambda_resource(
                sam_metadata_resource, logical_id, terraform_application_dir, python_command_name, output_directory_path
            )
            makefile_rules.append(makefile_rule)

    # generate makefile
    LOG.debug("Generate Makefile in %s", output_directory_path)
    generate_makefile(makefile_rules, output_directory_path)


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
            cfn_source_code_path = source_code

    if isinstance(source_code, list):
        # SAM CLI does not process multiple paths, so we will handle only the first value in this list
        # The first value can either be a string or dict so update source_code to be the first element of the list
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
        source_code = source_code[0]
        if not source_code:
            raise InvalidSamMetadataPropertiesException(
                f"The sam metadata resource {sam_metadata_resource_address} "
                f"should contain a valid lambda/lambda layer function "
                f"{src_code_attribute_name} in property {src_code_property_name}"
            )
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
