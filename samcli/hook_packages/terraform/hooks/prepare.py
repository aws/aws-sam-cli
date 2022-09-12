# pylint: disable=too-many-lines
"""
Terraform prepare hook implementation
"""

from dataclasses import dataclass
import json
import os
from json.decoder import JSONDecodeError
from pathlib import Path
import re
from subprocess import run, CalledProcessError
from typing import Any, Callable, Dict, List, Optional, Tuple
import hashlib
import logging
import shutil

from samcli.lib.hook.exceptions import PrepareHookException, InvalidSamMetadataPropertiesException
from samcli.lib.utils import osutils
from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
)

LOG = logging.getLogger(__name__)

TF_AWS_LAMBDA_FUNCTION = "aws_lambda_function"
AWS_PROVIDER_NAME = "registry.terraform.io/hashicorp/aws"
NULL_RESOURCE_PROVIDER_NAME = "registry.terraform.io/hashicorp/null"
SAM_METADATA_RESOURCE_TYPE = "null_resource"
SAM_METADATA_NAME_PREFIX = "sam_metadata_"

# max logical id len is 255
LOGICAL_ID_HASH_LEN = 8
LOGICAL_ID_MAX_HUMAN_LEN = 247

PropertyBuilder = Callable[[dict], Any]
PropertyBuilderMapping = Dict[str, PropertyBuilder]


@dataclass
class ResourceTranslator:
    cfn_name: str
    property_builder_mapping: PropertyBuilderMapping


@dataclass
class SamMetadataResource:
    current_module_address: Optional[str]
    resource: Dict


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

    try:
        # initialize terraform application
        LOG.info("Initializing Terraform application")
        run(["terraform", "init"], check=True, capture_output=True, cwd=terraform_application_dir)

        # get json output of terraform plan
        LOG.info("Creating terraform plan and getting JSON output")

        with osutils.tempfile_platform_independent() as temp_file:
            run(
                ["terraform", "plan", "-out", temp_file.name],
                check=True,
                capture_output=True,
                cwd=terraform_application_dir,
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

        # store in supplied output dir
        if not os.path.exists(output_dir_path):
            os.makedirs(output_dir_path, exist_ok=True)
        metadataFilePath = os.path.join(output_dir_path, "template.json")
        LOG.info("Finished generating metadata file. Storing in %s", metadataFilePath)
        with open(metadataFilePath, "w+") as metadata_file:
            json.dump(cfn_dict, metadata_file)

        return {"iac_applications": {"MainApplication": {"metadata_file": metadataFilePath}}}

    except CalledProcessError as e:
        # one of the subprocess.run calls resulted in non-zero exit code or some OS error
        LOG.debug(
            "Error running terraform command: \n" "cmd: %s \n" "stdout: %s \n" "stderr: %s \n",
            e.cmd,
            e.stdout,
            e.stderr,
        )
        raise PrepareHookException("There was an error while preparing the Terraform application.") from e
    except OSError as e:
        raise PrepareHookException(f"Unable to create directory {output_dir_path}") from e


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
    resources_attributes_to_be_updated = {CFN_AWS_LAMBDA_FUNCTION: ["Code"]}
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

    # to map s3 object sources to respective functions later
    s3_hash_to_source = {}

    sam_metadata_resources: List[SamMetadataResource] = []

    # create and iterate over queue of modules to handle child modules
    module_queue = [root_module]
    while module_queue:
        curr_module = module_queue.pop(0)
        curr_module_address = curr_module.get("address")

        # add child modules, if any, to queue
        child_modules = curr_module.get("child_modules")
        if child_modules:
            module_queue += child_modules

        # iterate over resources for current module
        resources = curr_module.get("resources", {})
        for resource in resources:
            resource_provider = resource.get("provider_name")
            resource_type = resource.get("type")
            resource_values = resource.get("values")
            resource_address = resource.get("address")
            resource_name = resource.get("name")

            if (
                resource_provider == NULL_RESOURCE_PROVIDER_NAME
                and resource_type == SAM_METADATA_RESOURCE_TYPE
                and resource_name.startswith(SAM_METADATA_NAME_PREFIX)
            ):
                sam_metadata_resources.append(SamMetadataResource(curr_module_address, resource))
                continue

            # only process supported provider
            if resource_provider != AWS_PROVIDER_NAME:
                continue

            # store S3 sources
            if resource_type == "aws_s3_object":
                obj_hash = _get_s3_object_hash(resource_values.get("bucket"), resource_values.get("key"))
                s3_hash_to_source[obj_hash] = resource_values.get("source")

            resource_translator = RESOURCE_TRANSLATOR_MAPPING.get(resource_type)
            # resource type not supported
            if not resource_translator:
                continue

            # translate TF resource "values" to CFN properties
            LOG.debug("Processing resource %s", resource_address)
            translated_properties = _translate_properties(resource_values, resource_translator.property_builder_mapping)
            translated_resource = {
                "Type": resource_translator.cfn_name,
                "Properties": translated_properties,
                "Metadata": {"SamResourceId": resource_address, "SkipBuild": True},
            }

            # build CFN logical ID from resource address
            logical_id = _build_cfn_logical_id(resource_address)

            # Add resource to cfn dict
            cfn_dict["Resources"][logical_id] = translated_resource

    # map s3 object sources to corresponding functions
    LOG.debug("Mapping S3 object sources to corresponding functions")
    _map_s3_sources_to_functions(s3_hash_to_source, cfn_dict.get("Resources", {}))

    if sam_metadata_resources:
        LOG.debug("Enrich the mapped resources with the sam metadata information and generate Makefile")
        _enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_dict.get("Resources", {}), output_directory_path, terraform_application_dir
        )
    else:
        LOG.debug("There is no sam metadata resources, no enrichment or Makefile is required")

    return cfn_dict


def _validate_referenced_resource_matches_sam_metadata_type(
    cfn_resource: dict, sam_metadata_attributes: dict, sam_metadata_resource_address: str, expected_package_type: str
) -> None:
    """
    Validate if the resource that match the resource name provided in the sam metadata resource matches the resource
    type provided in the metadata as well.

    Parameters
    ----------
    cfn_resource: dict
        The CFN resource that matches the sam metadata resource name
    sam_metadata_attributes: dict
        The sam metadata properties
    sam_metadata_resource_address: str
        The sam metadata resource address
    expected_package_type: str
        The expected lambda function package type.
    """
    cfn_resource_properties = cfn_resource.get("Properties", {})
    resource_type = sam_metadata_attributes.get("resource_type")
    cfn_resource_type = cfn_resource.get("Type")
    lambda_function_package_type = cfn_resource_properties.get("PackageType", ZIP)
    LOG.info(
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


def _get_lambda_function_source_code_path(
    sam_metadata_attributes: dict,
    sam_metadata_resource_address: str,
    project_root_dir: str,
    src_code_property_name: str,
    property_path_property_name: str,
    src_code_attribute_name: str,
) -> str:
    """
    Validate that sam metadata resource contains the valid metadata properties to get a lambda function source code.
    Parameters
    ----------
    sam_metadata_attributes: dict
        The sam metadata properties
    sam_metadata_resource_address: str
        The sam metadata resource address
    project_root_dir: str
        the terraform project root directory path
    src_code_property_name: str
        the sam metadata property name that contains the lambda function source code or docker context path
    property_path_property_name: str
        the sam metadata property name that contains the property to get the source code value if it was provided
        as json string
    src_code_attribute_name: str
        the lambda function source code or docker context to be used to raise the correct exception

    Returns
    -------
    str
        The lambda function source code or docker context paths
    """
    LOG.info(
        "Extract the %s from the sam metadata resource %s from property %s",
        src_code_attribute_name,
        sam_metadata_resource_address,
        src_code_property_name,
    )
    source_code = sam_metadata_attributes.get(src_code_property_name)
    source_code_property = sam_metadata_attributes.get(property_path_property_name)
    LOG.debug(
        "The found %s value is %s and property value is %s", src_code_attribute_name, source_code, source_code_property
    )
    if not source_code:
        raise InvalidSamMetadataPropertiesException(
            f"The sam metadata resource {sam_metadata_resource_address} should contain the lambda function "
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
                f"The sam metadata resource {sam_metadata_resource_address} should contain the lambda function "
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
                f"The sam metadata resource {sam_metadata_resource_address} should contain a valid lambda function "
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
                f"The sam metadata resource {sam_metadata_resource_address} should contain the lambda function "
                f"{src_code_attribute_name} in property {src_code_property_name}, and it should not be an empty list"
            )
        cfn_source_code_path = source_code[0]
        if not cfn_source_code_path:
            raise InvalidSamMetadataPropertiesException(
                f"The sam metadata resource {sam_metadata_resource_address} should contain a valid lambda function "
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
            f"lambda function {src_code_attribute_name} path"
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
    sam_metadata_attributes = sam_metadata_resource.get("values", {}).get("triggers", {})
    sam_metadata_resource_address = sam_metadata_resource.get("address")
    if not sam_metadata_resource_address:
        raise PrepareHookException(
            "Invalid Terraform plan output. The address property should not be null to any terraform resource."
        )

    LOG.info(
        "Enrich the ZIP lambda function %s using the metadata properties defined in resource %s",
        cfn_lambda_function_logical_id,
        sam_metadata_resource_address,
    )
    cfn_resource_properties = cfn_lambda_function.get("Properties", {})

    _validate_referenced_resource_matches_sam_metadata_type(
        cfn_lambda_function, sam_metadata_attributes, sam_metadata_resource_address, ZIP
    )

    cfn_source_code_path = _get_lambda_function_source_code_path(
        sam_metadata_attributes,
        sam_metadata_resource_address,
        terraform_application_dir,
        "original_source_code",
        "source_code_property",
        "source code",
    )
    cfn_resource_properties["Code"] = cfn_source_code_path
    if not cfn_lambda_function.get("Metadata", {}):
        cfn_lambda_function["Metadata"] = {}
    cfn_lambda_function["Metadata"]["SkipBuild"] = False
    cfn_lambda_function["Metadata"]["BuildMethod"] = "makefile"
    cfn_lambda_function["Metadata"]["ContextPath"] = output_directory_path
    cfn_lambda_function["Metadata"]["WorkingDirectory"] = terraform_application_dir
    # currently we set the terraform project root directory that contains all the terraform artifacts as the project
    # directory till we work on the custom hook properties, and add a property for this value.
    cfn_lambda_function["Metadata"]["ProjectRootDirectory"] = terraform_application_dir


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
    sam_metadata_attributes = sam_metadata_resource.get("values", {}).get("triggers", {})
    sam_metadata_resource_address = sam_metadata_resource.get("address")
    if not sam_metadata_resource_address:
        raise PrepareHookException(
            "Invalid Terraform plan output. The address property should not be null to any terraform resource."
        )
    cfn_resource_properties = cfn_lambda_function.get("Properties", {})

    LOG.info(
        "Enrich the IMAGE lambda function %s using the metadata properties defined in resource %s",
        cfn_lambda_function_logical_id,
        sam_metadata_resource_address,
    )

    _validate_referenced_resource_matches_sam_metadata_type(
        cfn_lambda_function, sam_metadata_attributes, sam_metadata_resource_address, IMAGE
    )

    cfn_docker_context_path = _get_lambda_function_source_code_path(
        sam_metadata_attributes,
        sam_metadata_resource_address,
        terraform_application_dir,
        "docker_context",
        "docker_context_property_path",
        "docker context",
    )
    cfn_docker_file = sam_metadata_attributes.get("docker_file")
    cfn_docker_build_args_string = sam_metadata_attributes.get("docker_build_args")
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

    cfn_docker_tag = sam_metadata_attributes.get("docker_tag")

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


def _enrich_resources_and_generate_makefile(
    sam_metadata_resources: List[SamMetadataResource],
    cfn_resources: Dict[str, Dict],
    output_directory_path: str,
    terraform_application_dir: str,
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
    """

    resources_types_enrichment_functions = {
        "ZIP_LAMBDA_FUNCTION": _enrich_zip_lambda_function,
        "IMAGE_LAMBDA_FUNCTION": _enrich_image_lambda_function,
    }

    makefile_rules = []
    for sam_metadata_resource in sam_metadata_resources:
        # enrich resource
        resource_type = sam_metadata_resource.resource.get("values", {}).get("triggers", {}).get("resource_type")
        sam_metadata_resource_address = sam_metadata_resource.resource.get("address")
        enrichment_function = resources_types_enrichment_functions.get(resource_type)
        if enrichment_function is None:
            raise InvalidSamMetadataPropertiesException(
                f"The resource type {resource_type} found in the sam metadata resource "
                f"{sam_metadata_resource_address} is not a correct resource type. The resource type should be one "
                f"of these values {resources_types_enrichment_functions.keys()}"
            )
        cfn_resource, logical_id = _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources)
        enrichment_function(
            sam_metadata_resource.resource,
            cfn_resource,
            logical_id,
            terraform_application_dir,
            output_directory_path,
        )

        # get makefile rule for resource
        makefile_rule = _generate_makefile_rule_for_lambda_resource(
            sam_metadata_resource, logical_id, terraform_application_dir
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

    # copy copy_terraform_built_artifacts.py script into output directory
    copy_terraform_built_artifacts_script_path = os.path.join(
        os.path.dirname(__file__), "copy_terraform_built_artifacts"
    )
    shutil.copy(copy_terraform_built_artifacts_script_path, output_directory_path)

    # create makefile
    makefilePath = os.path.join(output_directory_path, "Makefile")
    with open(makefilePath, "a+") as makefile:
        makefile.writelines(makefile_rules)


def _get_relevant_cfn_resource(
    sam_metadata_resource: SamMetadataResource, cfn_resources: Dict[str, Dict]
) -> Tuple[Dict, str]:
    """
    use the sam metadata resource name property to determine the resource address, and transform the address to logical
    id to use it to get the cfn_resource.

    Parameters
    ----------
    sam_metadata_resource: SamMetadataResource
        sam metadata resource that contain extra information about some resource.
    cfn_resources: Dict
        CloudFormation resources

    Returns
    -------
    tuple(Dict, str)
        The cfn resource that mentioned in the sam metadata resource, and the resource logical id
    """
    sam_metadata_resource_address = sam_metadata_resource.resource.get("address")
    resource_name = sam_metadata_resource.resource.get("values", {}).get("triggers", {}).get("resource_name")
    if not resource_name:
        raise InvalidSamMetadataPropertiesException(
            f"sam cli expects the sam metadata resource {sam_metadata_resource_address} to contain a resource name "
            f"that will be enriched using this metadata resource"
        )

    # the provided resource name will be always a postfix to the module address. The customer could not set a full
    # address within a module.
    LOG.info(
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
    logical_id = _build_cfn_logical_id(full_resource_address)
    cfn_resource = cfn_resources.get(logical_id)
    if cfn_resource:
        LOG.info("The CFN resource that match the input resource name %s is %s", resource_name, logical_id)
        return cfn_resource, logical_id

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
        else:
            # check for python 3, 3.7 or above
            # regex: search for 'Python', whitespace, '3.', digits 7-9 or 2+ digits, any digit or '.' 0+ times
            match = re.search(r"Python\s*3.([7-9]|\d{2,})[\d.]*", run_result.stdout)
            if not match:
                continue
            return command_name
    raise PrepareHookException("Python not found. Please ensure that python 3.7 or above is installed.")


def _generate_makefile_rule_for_lambda_resource(
    sam_metadata_resource: SamMetadataResource,
    logical_id: str,
    terraform_application_dir: str,
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

    Returns
    -------
    str
        The generated makefile rule
    """
    # TODO
    return ""


def _translate_properties(tf_properties: dict, property_builder_mapping: PropertyBuilderMapping) -> dict:
    """
    Translates the properties of a terraform resource into the equivalent properties of a CloudFormation resource

    Parameters
    ----------
    tf_properties: dict
        The terraform properties to translate
    property_builder_mappping: PropertyBuilderMapping
        A mapping of the CloudFormation property name to a function for building that property

    Returns
    -------
    dict
        The CloudFormation properties resulting from translating tf_properties
    """
    cfn_properties = {}
    for cfn_property_name, cfn_property_builder in property_builder_mapping.items():
        cfn_property_value = cfn_property_builder(tf_properties)
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
    return lambda properties: properties.get(property_name)


def _build_lambda_function_environment_property(tf_properties: dict) -> Optional[dict]:
    """
    Builds the Environment property of a CloudFormation AWS Lambda Function out of the
    properties of the equivalent terraform resource

    Parameters
    ----------
    tf_properties: dict
        Properties of the terraform AWS Lambda function resource

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


def _build_lambda_function_code_property(tf_properties: dict) -> Any:
    """
    Builds the Code property of a CloudFormation AWS Lambda Function out of the
    properties of the equivalent terraform resource

    Parameters
    ----------
    tf_properties: dict
        Properties of the terraform AWS Lambda function resource

    Returns
    -------
    dict
        The built Code property of a CloudFormation AWS Lambda Function resource
    """
    filename = tf_properties.get("filename")
    if filename:
        return filename

    code = {}
    tf_cfn_prop_names = [("s3_bucket", "S3Bucket"), ("s3_key", "S3Key"), ("image_uri", "ImageUri")]
    for tf_prop_name, cfn_prop_name in tf_cfn_prop_names:
        tf_prop_value = tf_properties.get(tf_prop_name)
        if tf_prop_value is not None:
            code[cfn_prop_name] = tf_prop_value
    return code


def _build_lambda_function_image_config_property(tf_properties: dict) -> Optional[dict]:
    """
    Builds the ImageConfig property of a CloudFormation AWS Lambda Function out of the
    properties of the equivalent terraform resource

    Parameters
    ----------
    tf_properties: dict
        Properties of the terraform AWS Lambda function resource

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
            f"SAM CLI expects that the value of image_config of aws_lambda_function resource in "
            f"the terraform plan output to be of type list instead of {type(image_config)}"
        )
    if len(image_config) > 1:
        raise PrepareHookException(
            f"SAM CLI expects that there is only one item in the  image_config property of "
            f"aws_lambda_function resource in the terraform plan output, but there are "
            f"{len(image_config)} items"
        )
    return True


AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "FunctionName": _get_property_extractor("function_name"),
    "Architectures": _get_property_extractor("architectures"),
    "Environment": _build_lambda_function_environment_property,
    "Code": _build_lambda_function_code_property,
    "Handler": _get_property_extractor("handler"),
    "PackageType": _get_property_extractor("package_type"),
    "Runtime": _get_property_extractor("runtime"),
    "Layers": _get_property_extractor("layers"),
    "Timeout": _get_property_extractor("timeout"),
    "ImageConfig": _build_lambda_function_image_config_property,
}

RESOURCE_TRANSLATOR_MAPPING: Dict[str, ResourceTranslator] = {
    TF_AWS_LAMBDA_FUNCTION: ResourceTranslator(CFN_AWS_LAMBDA_FUNCTION, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING),
}


def _build_cfn_logical_id(tf_address: str) -> str:
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


def _get_s3_object_hash(bucket: str, key: str) -> str:
    """
    Creates a hash for an AWS S3 object out of the bucket and key

    Parameters
    ----------
    bucket: str
        bucket for the S3 object
    key: str
        key for the S3 object

    Returns
    -------
    str
        hash for the given bucket and key
    """
    md5 = hashlib.md5()
    md5.update(bucket.encode())
    md5.update(key.encode())
    return md5.hexdigest()


def _map_s3_sources_to_functions(s3_hash_to_source: Dict[str, str], cfn_resources: Dict[str, Any]) -> None:
    """
    Maps the source property of terraform AWS S3 object resources into the the Code property of
    CloudFormation AWS Lambda Function resources

    Parameters
    ----------
    s3_hash_to_source: Dict[str, str]
        Mapping of S3 object hash to S3 object source
    cfn_resources: dict
        CloudFormation resources
    """
    for _, resource in cfn_resources.items():
        if resource.get("Type") == CFN_AWS_LAMBDA_FUNCTION:
            code = resource.get("Properties").get("Code")

            # mapping not possible if function doesn't have bucket and key
            if isinstance(code, str):
                continue

            bucket = code.get("S3Bucket")
            key = code.get("S3Key")
            if bucket and key:
                obj_hash = _get_s3_object_hash(bucket, key)
                source = s3_hash_to_source.get(obj_hash)
                if source:
                    tf_address = resource.get("Metadata", {}).get("SamResourceId")
                    LOG.debug(
                        "Found S3 object resource with matching bucket and key for function %s."
                        " Setting function's Code property to the matching S3 object's source: %s",
                        tf_address,
                        source,
                    )
                    resource["Properties"]["Code"] = source
