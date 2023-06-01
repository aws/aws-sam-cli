from typing import List

from samcli.hook_packages.terraform.hooks.prepare.property_builder import (
    TF_AWS_API_GATEWAY_AUTHORIZER,
    TF_AWS_API_GATEWAY_INTEGRATION,
    TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE,
    TF_AWS_API_GATEWAY_METHOD,
    TF_AWS_API_GATEWAY_RESOURCE,
    TF_AWS_API_GATEWAY_REST_API,
    TF_AWS_API_GATEWAY_STAGE,
    TF_AWS_LAMBDA_FUNCTION,
    TF_AWS_LAMBDA_LAYER_VERSION,
)
from samcli.hook_packages.terraform.hooks.prepare.resource_linking import (
    _link_gateway_authorizer_to_lambda_function,
    _link_gateway_authorizer_to_rest_api,
    _link_gateway_integration_responses_to_gateway_resource,
    _link_gateway_integration_responses_to_gateway_rest_apis,
    _link_gateway_integrations_to_function_resource,
    _link_gateway_integrations_to_gateway_resource,
    _link_gateway_integrations_to_gateway_rest_apis,
    _link_gateway_method_to_gateway_authorizer,
    _link_gateway_method_to_gateway_resource,
    _link_gateway_methods_to_gateway_rest_apis,
    _link_gateway_resources_to_gateway_rest_apis,
    _link_gateway_stage_to_rest_api,
    _link_lambda_functions_to_layers,
)
from samcli.hook_packages.terraform.hooks.prepare.types import LinkingPairCaller

RESOURCE_LINKS: List[LinkingPairCaller] = [
    LinkingPairCaller(
        source=TF_AWS_LAMBDA_FUNCTION, dest=TF_AWS_LAMBDA_LAYER_VERSION, linking_func=_link_lambda_functions_to_layers
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_METHOD,
        dest=TF_AWS_API_GATEWAY_REST_API,
        linking_func=_link_gateway_methods_to_gateway_rest_apis,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_RESOURCE,
        dest=TF_AWS_API_GATEWAY_REST_API,
        linking_func=_link_gateway_resources_to_gateway_rest_apis,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_STAGE, dest=TF_AWS_API_GATEWAY_REST_API, linking_func=_link_gateway_stage_to_rest_api
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_METHOD,
        dest=TF_AWS_API_GATEWAY_RESOURCE,
        linking_func=_link_gateway_method_to_gateway_resource,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_INTEGRATION,
        dest=TF_AWS_API_GATEWAY_REST_API,
        linking_func=_link_gateway_integrations_to_gateway_rest_apis,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_INTEGRATION,
        dest=TF_AWS_API_GATEWAY_RESOURCE,
        linking_func=_link_gateway_integrations_to_gateway_resource,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_INTEGRATION,
        dest=TF_AWS_LAMBDA_FUNCTION,
        linking_func=_link_gateway_integrations_to_function_resource,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE,
        dest=TF_AWS_API_GATEWAY_REST_API,
        linking_func=_link_gateway_integration_responses_to_gateway_rest_apis,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_INTEGRATION_RESPONSE,
        dest=TF_AWS_API_GATEWAY_RESOURCE,
        linking_func=_link_gateway_integration_responses_to_gateway_resource,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_AUTHORIZER,
        dest=TF_AWS_LAMBDA_FUNCTION,
        linking_func=_link_gateway_authorizer_to_lambda_function,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_AUTHORIZER,
        dest=TF_AWS_API_GATEWAY_REST_API,
        linking_func=_link_gateway_authorizer_to_rest_api,
    ),
    LinkingPairCaller(
        source=TF_AWS_API_GATEWAY_METHOD,
        dest=TF_AWS_API_GATEWAY_AUTHORIZER,
        linking_func=_link_gateway_method_to_gateway_authorizer,
    ),
]
