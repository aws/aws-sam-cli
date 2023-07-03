"""
Terraform translate to CFN implementation

This method contains the logic required to translate the `terraform show` JSON output into a Cloudformation template
"""
import hashlib
import logging
from typing import Any, Dict, Iterator, List, Tuple, Type, Union

from samcli.hook_packages.terraform.hooks.prepare.constants import (
    CFN_CODE_PROPERTIES,
    SAM_METADATA_RESOURCE_NAME_ATTRIBUTE,
)
from samcli.hook_packages.terraform.hooks.prepare.enrich import enrich_resources_and_generate_makefile
from samcli.hook_packages.terraform.hooks.prepare.property_builder import (
    REMOTE_DUMMY_VALUE,
    RESOURCE_TRANSLATOR_MAPPING,
    TF_AWS_API_GATEWAY_INTEGRATION,
    TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE,
    TF_AWS_API_GATEWAY_METHOD,
    TF_AWS_API_GATEWAY_REST_API,
    PropertyBuilderMapping,
)
from samcli.hook_packages.terraform.hooks.prepare.resource_linking import (
    _build_module,
    _resolve_resource_attribute,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.apigw import (
    RESTAPITranslationValidator,
    add_integration_responses_to_methods,
    add_integrations_to_methods,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.internal import INTERNAL_PREFIX
from samcli.hook_packages.terraform.hooks.prepare.resources.resource_links import RESOURCE_LINKS
from samcli.hook_packages.terraform.hooks.prepare.resources.resource_properties import get_resource_property_mapping
from samcli.hook_packages.terraform.hooks.prepare.types import (
    CodeResourceProperties,
    ConstantValue,
    References,
    ResolvedReference,
    ResourceProperties,
    ResourceTranslationProperties,
    ResourceTranslationValidator,
    SamMetadataResource,
    TFModule,
    TFResource,
)
from samcli.hook_packages.terraform.hooks.prepare.utilities import get_configuration_address
from samcli.hook_packages.terraform.lib.utils import (
    _calculate_configuration_attribute_value_hash,
    build_cfn_logical_id,
    get_sam_metadata_planned_resource_value_attribute,
)
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.colors import Colored, Colors
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION

SAM_METADATA_RESOURCE_TYPE = "null_resource"
SAM_METADATA_NAME_PREFIX = "sam_metadata_"

AWS_PROVIDER_NAME = "registry.terraform.io/hashicorp/aws"
NULL_RESOURCE_PROVIDER_NAME = "registry.terraform.io/hashicorp/null"

LOG = logging.getLogger(__name__)

TRANSLATION_VALIDATORS: Dict[str, Type[ResourceTranslationValidator]] = {
    TF_AWS_API_GATEWAY_REST_API: RESTAPITranslationValidator,
}


def _get_modules(root_module: dict, root_tf_module: TFModule) -> Iterator[Tuple[dict, TFModule]]:
    """
    Iterator helper method to find any child modules for processing.

    Parameters
    ----------
    root_module: dict
        The root level planned values dictionary
    root_tf_module: TFModule
        The TFModule class representation of the configuration values

    Yields
    ------
    Tuple[dict, TFModule]
        A tuple of the current module's planned values and TFModule representation of configuration values
    """
    queue = [(root_module, root_tf_module)]

    while queue:
        modules = queue.pop(0)

        yield modules

        _add_child_modules_to_queue(*modules, queue)


def _check_unresolvable_values(root_module: dict, root_tf_module: TFModule) -> None:
    """
    Checks the planned values and configuration values if there are any properties
    that are unresolved, or unknown, until the Terraform project is applied.

    Parameters
    ----------
    root_module: dict
        The root level planned values dictionary
    root_tf_module: TFModule
        The TFModule class representation of the configuration values
    """

    for curr_module, curr_tf_module in _get_modules(root_module, root_tf_module):
        # iterate over resources for current module
        for resource in curr_module.get("resources", []):
            resource_type = resource.get("type")
            resource_name = resource.get("name")
            resource_mode = resource.get("mode")

            resource_mapper = RESOURCE_TRANSLATOR_MAPPING.get(resource_type)
            if not resource_mapper:
                continue

            resource_values = resource.get("values")
            resource_address = (
                f"data.{resource_type}.{resource_name}"
                if resource_mode == "data"
                else f"{resource_type}.{resource_name}"
            )

            config_resource_address = get_configuration_address(resource_address)
            config_resource = curr_tf_module.resources[config_resource_address]

            for prop_builder in resource_mapper.property_builder_mapping.values():
                planned_values = prop_builder(resource_values, config_resource)
                config_values = prop_builder(config_resource.attributes, config_resource)

                if config_values and not planned_values:
                    LOG.warning(
                        Colored().color_log(
                            msg="\nUnresolvable attributes discovered in project, "
                            "run terraform apply to resolve them.\n",
                            color=Colors.WARNING,
                        ),
                        extra=dict(markup=True),
                    )

                    return


def translate_to_cfn(tf_json: dict, output_directory_path: str, terraform_application_dir: str) -> dict:
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

    resource_property_mapping: Dict[str, ResourceProperties] = get_resource_property_mapping()

    _check_unresolvable_values(root_module, root_tf_module)

    # create and iterate over queue of modules to handle child modules
    for curr_module, curr_tf_module in _get_modules(root_module, root_tf_module):
        curr_module_address = curr_module.get("address")

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
            config_resource_address = get_configuration_address(resource_address)
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
            translated_resource: Dict = {
                "Type": resource_translator.cfn_name,
                "Properties": translated_properties,
                "Metadata": {"SamResourceId": resource_full_address},
            }

            # Only set the SkipBuild metadata if it's a resource that can be built
            if resource_translator.cfn_name in CFN_CODE_PROPERTIES:
                translated_resource["Metadata"]["SkipBuild"] = True

            # build CFN logical ID from resource address
            logical_id = build_cfn_logical_id(resource_full_address)

            # Add resource to cfn dict
            if not translated_resource.get("Type", "").startswith(INTERNAL_PREFIX):
                # Internal resources are ones used for the purpose of translation, they are not real CFN resources.
                # These are usually resources that exist in other IaCs that don't map 1:1 with CFN resources, but their
                # properties need to be mapped to other, existing CFN resources.
                cfn_dict["Resources"][logical_id] = translated_resource

            resource_translation_properties = ResourceTranslationProperties(
                resource=resource,
                translated_resource=translated_resource,
                config_resource=config_resource,
                logical_id=logical_id,
                resource_full_address=resource_full_address,
            )
            if resource_type in resource_property_mapping:
                resource_properties: ResourceProperties = resource_property_mapping[resource_type]
                resource_properties.collect(resource_translation_properties)
                if isinstance(resource_properties, CodeResourceProperties):
                    resource_properties.add_lambda_resources_to_code_map(
                        resource_translation_properties, translated_properties, lambda_resources_to_code_map
                    )

            if resource_type in TRANSLATION_VALIDATORS:
                validator = TRANSLATION_VALIDATORS[resource_type](resource=resource, config_resource=config_resource)
                validator.validate()

    # map s3 object sources to corresponding functions
    LOG.debug("Mapping S3 object sources to corresponding functions")
    _map_s3_sources_to_functions(s3_hash_to_source, cfn_dict.get("Resources", {}), lambda_resources_to_code_map)

    _handle_linking(resource_property_mapping)

    add_integrations_to_methods(
        resource_property_mapping.get(TF_AWS_API_GATEWAY_METHOD, ResourceProperties()).cfn_resources,
        resource_property_mapping.get(TF_AWS_API_GATEWAY_INTEGRATION, ResourceProperties()).cfn_resources,
    )

    add_integration_responses_to_methods(
        resource_property_mapping.get(TF_AWS_API_GATEWAY_METHOD, ResourceProperties()).cfn_resources,
        resource_property_mapping.get(TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE, ResourceProperties()).cfn_resources,
    )

    if sam_metadata_resources:
        LOG.debug("Enrich the mapped resources with the sam metadata information and generate Makefile")
        enrich_resources_and_generate_makefile(
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


def _handle_linking(resource_property_mapping: Dict[str, ResourceProperties]) -> None:
    for links in RESOURCE_LINKS:
        links.linking_func(
            resource_property_mapping[links.source].terraform_config,
            resource_property_mapping[links.source].cfn_resources,
            resource_property_mapping[links.dest].terraform_resources,
        )


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
                get_configuration_address(child_module["address"]) if "address" in child_module else None
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


def _translate_properties(
    tf_properties: dict, property_builder_mapping: PropertyBuilderMapping, resource: TFResource
) -> dict:
    """
    Translates the properties of a terraform resource into the equivalent properties of a CloudFormation resource

    Parameters
    ----------
    tf_properties: dict
        The terraform properties to translate
    property_builder_mapping: PropertyBuilderMapping
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
