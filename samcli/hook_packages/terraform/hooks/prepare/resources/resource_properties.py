"""Module for getting the resource property mappings for various resource types"""

from typing import Dict

from samcli.hook_packages.terraform.hooks.prepare.constants import (
    TF_AWS_API_GATEWAY_AUTHORIZER,
    TF_AWS_API_GATEWAY_INTEGRATION,
    TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE,
    TF_AWS_API_GATEWAY_METHOD,
    TF_AWS_API_GATEWAY_RESOURCE,
    TF_AWS_API_GATEWAY_REST_API,
    TF_AWS_API_GATEWAY_STAGE,
    TF_AWS_API_GATEWAY_V2_API,
    TF_AWS_API_GATEWAY_V2_AUTHORIZER,
    TF_AWS_API_GATEWAY_V2_INTEGRATION,
    TF_AWS_API_GATEWAY_V2_ROUTE,
    TF_AWS_API_GATEWAY_V2_STAGE,
    TF_AWS_LAMBDA_FUNCTION,
    TF_AWS_LAMBDA_LAYER_VERSION,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.apigw import (
    ApiGatewayAuthorizerProperties,
    ApiGatewayMethodProperties,
    ApiGatewayResourceProperties,
    ApiGatewayRestApiProperties,
    ApiGatewayStageProperties,
    ApiGatewayV2ApiProperties,
    ApiGatewayV2AuthorizerProperties,
    ApiGatewayV2IntegrationProperties,
    ApiGatewayV2RouteProperties,
    ApiGatewayV2StageProperties,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.internal import (
    InternalApiGatewayIntegrationProperties,
    InternalApiGatewayIntegrationResponseProperties,
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
        TF_AWS_API_GATEWAY_RESOURCE: ApiGatewayResourceProperties(),
        TF_AWS_API_GATEWAY_REST_API: ApiGatewayRestApiProperties(),
        TF_AWS_API_GATEWAY_METHOD: ApiGatewayMethodProperties(),
        TF_AWS_API_GATEWAY_STAGE: ApiGatewayStageProperties(),
        TF_AWS_API_GATEWAY_INTEGRATION: InternalApiGatewayIntegrationProperties(),
        TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE: InternalApiGatewayIntegrationResponseProperties(),
        TF_AWS_API_GATEWAY_AUTHORIZER: ApiGatewayAuthorizerProperties(),
        TF_AWS_API_GATEWAY_V2_ROUTE: ApiGatewayV2RouteProperties(),
        TF_AWS_API_GATEWAY_V2_INTEGRATION: ApiGatewayV2IntegrationProperties(),
        TF_AWS_API_GATEWAY_V2_API: ApiGatewayV2ApiProperties(),
        TF_AWS_API_GATEWAY_V2_AUTHORIZER: ApiGatewayV2AuthorizerProperties(),
        TF_AWS_API_GATEWAY_V2_STAGE: ApiGatewayV2StageProperties(),
    }
