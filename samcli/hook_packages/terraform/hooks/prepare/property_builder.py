"""
Terraform prepare property builder
"""
import logging
from json import loads
from json.decoder import JSONDecodeError
from typing import Any, Dict, Optional

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import _resolve_resource_attribute
from samcli.hook_packages.terraform.hooks.prepare.resources.internal import (
    INTERNAL_API_GATEWAY_INTEGRATION,
    INTERNAL_API_GATEWAY_INTEGRATION_RESPONSE,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    PropertyBuilder,
    PropertyBuilderMapping,
    ResourceTranslator,
    TFResource,
)
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resources import AWS_APIGATEWAY_AUTHORIZER as CFN_AWS_APIGATEWAY_AUTHORIZER
from samcli.lib.utils.resources import AWS_APIGATEWAY_METHOD as CFN_AWS_APIGATEWAY_METHOD
from samcli.lib.utils.resources import AWS_APIGATEWAY_RESOURCE as CFN_AWS_APIGATEWAY_RESOURCE
from samcli.lib.utils.resources import AWS_APIGATEWAY_RESTAPI as CFN_AWS_APIGATEWAY_RESTAPI
from samcli.lib.utils.resources import AWS_APIGATEWAY_STAGE as CFN_AWS_APIGATEWAY_STAGE
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION
from samcli.lib.utils.resources import AWS_LAMBDA_LAYERVERSION as CFN_AWS_LAMBDA_LAYER_VERSION

LOG = logging.getLogger(__name__)

REMOTE_DUMMY_VALUE = "<<REMOTE DUMMY VALUE - RAISE ERROR IF IT IS STILL THERE>>"
TF_AWS_LAMBDA_FUNCTION = "aws_lambda_function"
TF_AWS_LAMBDA_LAYER_VERSION = "aws_lambda_layer_version"

TF_AWS_API_GATEWAY_RESOURCE = "aws_api_gateway_resource"
TF_AWS_API_GATEWAY_REST_API = "aws_api_gateway_rest_api"
TF_AWS_API_GATEWAY_STAGE = "aws_api_gateway_stage"
TF_AWS_API_GATEWAY_METHOD = "aws_api_gateway_method"
TF_AWS_API_GATEWAY_INTEGRATION = "aws_api_gateway_integration"
TF_AWS_API_GATEWAY_AUTHORIZER = "aws_api_gateway_authorizer"
TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE = "aws_api_gateway_method_response"


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


def _get_json_body(tf_properties: dict, resource: TFResource) -> Any:
    """
    Gets the JSON formatted body value from the API Gateway if there is one

    Parameters
    ----------
    tf_properties: dict
        Properties of the terraform AWS Lambda function resource
    resource: TFResource
        Configuration terraform resource

    Returns
    -------
    Any
        Returns a dictonary if there is a valid body to parse, otherwise return original value
    """
    body = tf_properties.get("body")

    if isinstance(body, str):
        try:
            return loads(body)
        except JSONDecodeError:
            pass

    LOG.debug(f"Failed to load JSON body for API Gateway body, returning original value: '{body}'")

    return body


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
    "MemorySize": _get_property_extractor("memory_size"),
    "ImageConfig": _build_lambda_function_image_config_property,
}

AWS_LAMBDA_LAYER_VERSION_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "LayerName": _get_property_extractor("layer_name"),
    "CompatibleRuntimes": _get_property_extractor("compatible_runtimes"),
    "CompatibleArchitectures": _get_property_extractor("compatible_architectures"),
    "Content": _build_code_property,
}

AWS_API_GATEWAY_REST_API_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "Name": _get_property_extractor("name"),
    "Body": _get_json_body,
    "Parameters": _get_property_extractor("parameters"),
    "BinaryMediaTypes": _get_property_extractor("binary_media_types"),
}

AWS_API_GATEWAY_STAGE_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "RestApiId": _get_property_extractor("rest_api_id"),
    "StageName": _get_property_extractor("stage_name"),
    "Variables": _get_property_extractor("variables"),
}

AWS_API_GATEWAY_RESOURCE_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "RestApiId": _get_property_extractor("rest_api_id"),
    "ParentId": _get_property_extractor("parent_id"),
    "PathPart": _get_property_extractor("path_part"),
}

AWS_API_GATEWAY_METHOD_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "RestApiId": _get_property_extractor("rest_api_id"),
    "ResourceId": _get_property_extractor("resource_id"),
    "HttpMethod": _get_property_extractor("http_method"),
    "OperationName": _get_property_extractor("operation_name"),
    "AuthorizerId": _get_property_extractor("authorizer_id"),
    "AuthorizationType": _get_property_extractor("authorization"),
}

AWS_API_GATEWAY_INTEGRATION_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "RestApiId": _get_property_extractor("rest_api_id"),
    "ResourceId": _get_property_extractor("resource_id"),
    "HttpMethod": _get_property_extractor("http_method"),
    "Uri": _get_property_extractor("uri"),
    "Type": _get_property_extractor("type"),
    "ContentHandling": _get_property_extractor("content_handling"),
    "ConnectionType": _get_property_extractor("connection_type"),
}

AWS_API_GATEWAY_AUTHORIZER_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "Name": _get_property_extractor("name"),
    "RestApiId": _get_property_extractor("rest_api_id"),
    "AuthorizerUri": _get_property_extractor("authorizer_uri"),
    "IdentitySource": _get_property_extractor("identity_source"),
    "Type": _get_property_extractor("type"),
    "IdentityValidationExpression": _get_property_extractor("identity_validation_expression"),
}

AWS_API_GATEWAY_INTEGRATION_RESPONSE_PROPERTY_BUILDER_MAPPING: PropertyBuilderMapping = {
    "RestApiId": _get_property_extractor("rest_api_id"),
    "ResourceId": _get_property_extractor("resource_id"),
    "HttpMethod": _get_property_extractor("http_method"),
    "ResponseParameters": _get_property_extractor("response_parameters"),
}

RESOURCE_TRANSLATOR_MAPPING: Dict[str, ResourceTranslator] = {
    TF_AWS_LAMBDA_FUNCTION: ResourceTranslator(CFN_AWS_LAMBDA_FUNCTION, AWS_LAMBDA_FUNCTION_PROPERTY_BUILDER_MAPPING),
    TF_AWS_LAMBDA_LAYER_VERSION: ResourceTranslator(
        CFN_AWS_LAMBDA_LAYER_VERSION, AWS_LAMBDA_LAYER_VERSION_PROPERTY_BUILDER_MAPPING
    ),
    TF_AWS_API_GATEWAY_REST_API: ResourceTranslator(
        CFN_AWS_APIGATEWAY_RESTAPI, AWS_API_GATEWAY_REST_API_PROPERTY_BUILDER_MAPPING
    ),
    TF_AWS_API_GATEWAY_STAGE: ResourceTranslator(
        CFN_AWS_APIGATEWAY_STAGE, AWS_API_GATEWAY_STAGE_PROPERTY_BUILDER_MAPPING
    ),
    TF_AWS_API_GATEWAY_RESOURCE: ResourceTranslator(
        CFN_AWS_APIGATEWAY_RESOURCE, AWS_API_GATEWAY_RESOURCE_PROPERTY_BUILDER_MAPPING
    ),
    TF_AWS_API_GATEWAY_METHOD: ResourceTranslator(
        CFN_AWS_APIGATEWAY_METHOD, AWS_API_GATEWAY_METHOD_PROPERTY_BUILDER_MAPPING
    ),
    TF_AWS_API_GATEWAY_INTEGRATION: ResourceTranslator(
        INTERNAL_API_GATEWAY_INTEGRATION, AWS_API_GATEWAY_INTEGRATION_PROPERTY_BUILDER_MAPPING
    ),
    TF_AWS_API_GATEWAY_AUTHORIZER: ResourceTranslator(
        CFN_AWS_APIGATEWAY_AUTHORIZER, AWS_API_GATEWAY_AUTHORIZER_PROPERTY_BUILDER_MAPPING
    ),
    TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE: ResourceTranslator(
        INTERNAL_API_GATEWAY_INTEGRATION_RESPONSE, AWS_API_GATEWAY_INTEGRATION_RESPONSE_PROPERTY_BUILDER_MAPPING
    ),
}
