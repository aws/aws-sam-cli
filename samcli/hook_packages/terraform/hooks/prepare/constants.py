"""
Constants related to the Terraform prepare hook.
"""

import re

from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION
from samcli.lib.utils.resources import AWS_LAMBDA_LAYERVERSION as CFN_AWS_LAMBDA_LAYER_VERSION

SAM_METADATA_RESOURCE_NAME_ATTRIBUTE = "resource_name"

CFN_CODE_PROPERTIES = {
    CFN_AWS_LAMBDA_FUNCTION: "Code",
    CFN_AWS_LAMBDA_LAYER_VERSION: "Content",
}
COMPILED_REGULAR_EXPRESSION = re.compile(r"\[[^\[\]]*\]")
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
TF_AWS_API_GATEWAY_V2_API = "aws_apigatewayv2_api"
TF_AWS_API_GATEWAY_V2_ROUTE = "aws_apigatewayv2_route"
TF_AWS_API_GATEWAY_V2_STAGE = "aws_apigatewayv2_stage"
TF_AWS_API_GATEWAY_V2_INTEGRATION = "aws_apigatewayv2_integration"
TF_AWS_API_GATEWAY_V2_AUTHORIZER = "aws_apigatewayv2_authorizer"
