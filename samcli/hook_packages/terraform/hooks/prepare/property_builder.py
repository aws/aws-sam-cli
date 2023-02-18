"""
Terraform prepare property builder
"""
from typing import Any, Dict, Optional

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import _resolve_resource_attribute
from samcli.hook_packages.terraform.hooks.prepare.types import (
    PropertyBuilder,
    PropertyBuilderMapping,
    ResourceTranslator,
    TFResource,
)
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION
from samcli.lib.utils.resources import AWS_LAMBDA_LAYERVERSION as CFN_AWS_LAMBDA_LAYER_VERSION

REMOTE_DUMMY_VALUE = "<<REMOTE DUMMY VALUE - RAISE ERROR IF IT IS STILL THERE>>"
TF_AWS_LAMBDA_FUNCTION = "aws_lambda_function"
TF_AWS_LAMBDA_LAYER_VERSION = "aws_lambda_layer_version"


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
