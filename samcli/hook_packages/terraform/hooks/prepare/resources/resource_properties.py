"""Module for getting the resource property mappings for various resource types"""
from typing import Dict

from samcli.hook_packages.terraform.hooks.prepare.property_builder import (
    TF_AWS_API_GATEWAY_METHOD,
    TF_AWS_API_GATEWAY_REST_API,
    TF_AWS_LAMBDA_FUNCTION,
    TF_AWS_LAMBDA_LAYER_VERSION,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.apigw import (
    ApiGatewayMethodProperties,
    ApiGatewayRestApiProperties,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.lambda_function import LambdaFunctionProperties
from samcli.hook_packages.terraform.hooks.prepare.resources.lambda_layers import LambdaLayerVersionProperties
from samcli.hook_packages.terraform.hooks.prepare.types import ResourceProperties


def get_resource_property_mapping() -> Dict[str, ResourceProperties]:
    """
    Get a map containing the class for handling resource
    property translations for a specific resource type

    Returns
    -------
    Dict[str, ResourceProperties]
        A mapping between the Terraform resource type and the
        ResourceProperties handling class for that resource type
    """
    return {
        TF_AWS_LAMBDA_LAYER_VERSION: LambdaLayerVersionProperties(),
        TF_AWS_LAMBDA_FUNCTION: LambdaFunctionProperties(),
        TF_AWS_API_GATEWAY_REST_API: ApiGatewayRestApiProperties(),
        TF_AWS_API_GATEWAY_METHOD: ApiGatewayMethodProperties(),
    }
