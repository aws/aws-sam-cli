"""
Terraform prepare hook implementation
"""

from dataclasses import dataclass
import json
import os
from subprocess import run, CalledProcessError
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, List, Optional
import hashlib
import logging

from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
)

LOG = logging.getLogger(__name__)

TF_AWS_LAMBDA_FUNCTION = "aws_lambda_function"
PROVIDER_NAME = "registry.terraform.io/hashicorp/aws"

# max logical id len is 255
LOGICAL_ID_HASH_LEN = 8
LOGICAL_ID_MAX_HUMAN_LEN = 247

PropertyBuilder = Callable[[dict], Any]
PropertyBuilderMapping = Dict[str, PropertyBuilder]


@dataclass
class ResourceTranslator:
    cfn_name: str
    property_builder_mapping: PropertyBuilderMapping


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
    if not output_dir_path:
        raise PrepareHookException("OutputDirPath was not supplied")

    try:
        # initialize terraform application
        run(["terraform", "init"], check=True, capture_output=True)

        # get json output of terraform plan
        with NamedTemporaryFile() as temp_file:
            run(["terraform", "plan", "-out", temp_file.name], check=True, capture_output=True)
            result = run(["terraform", "show", "-json", temp_file.name], check=True, capture_output=True)
        tf_json = json.loads(result.stdout)

        # convert terraform to cloudformation
        cfn_dict = _translate_to_cfn(tf_json)

        # store in supplied output dir
        if not os.path.exists(output_dir_path):
            os.mkdir(output_dir_path)
        metadataFilePath = os.path.join(output_dir_path, "template.json")
        with open(metadataFilePath, "w+") as metadata_file:
            json.dump(cfn_dict, metadata_file)

        return {"iac_applications": {"MainApplication": {"metadata_file": metadataFilePath}}}

    except (CalledProcessError, OSError) as e:
        # one of the subprocess.run calls resulted in non-zero exit code or some OS error
        raise PrepareHookException("There was an error while preparing the Terraform application.") from e


def _translate_to_cfn(tf_json: dict) -> dict:
    """
    Translates the json output of a terraform show into CloudFormation

    Parameters
    ----------
    tf_json: dict
        A terraform show json output

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

    # create and iterate over queue of modules to handle child modules
    module_queue = [root_module]
    while module_queue:
        curr_module = module_queue.pop()

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

            # only process supported provider
            if resource_provider != PROVIDER_NAME:
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
            LOG.debug("Translating resource: %s", resource_address)
            translated_properties = _translate_properties(resource_values, resource_translator.property_builder_mapping)
            translated_resource = {
                "Type": resource_translator.cfn_name,
                "Properties": translated_properties,
                "Metadata": {"SamResourceId": resource_address, "SkipBuild": True},
            }
            LOG.debug("Translated resource: %s", translated_resource)

            # build CFN logical ID from resource address
            logical_id = _build_cfn_logical_id(resource_address)

            # Add resource to cfn dict
            cfn_dict["Resources"][logical_id] = translated_resource

    # map s3 object sources to corresponding functions
    LOG.debug("Mapping S3 object sources to corresponding functions")
    _map_s3_sources_to_functions(s3_hash_to_source, cfn_dict["Resources"])
    LOG.debug("Final translated CloudFormation: %s", cfn_dict)

    return cfn_dict


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
    tf_cfn_prop_names = [("s3_bucket", "S3Bucket"), ("s3_key", "S3Key")]
    for tf_prop_name, cfn_prop_name in tf_cfn_prop_names:
        tf_prop_value = tf_properties.get(tf_prop_name)
        if tf_prop_value is not None:
            code[cfn_prop_name] = tf_prop_value
    return code


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
            if isinstance(code, str):
                continue

            bucket = code.get("S3Bucket")
            key = code.get("S3Key")
            if bucket and key:
                obj_hash = _get_s3_object_hash(bucket, key)
                source = s3_hash_to_source.get(obj_hash)
                if source:
                    resource["Properties"]["Code"] = source
