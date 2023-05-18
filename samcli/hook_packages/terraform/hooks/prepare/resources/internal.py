"""Module containing logic specific to internal resources handling during the prepare hook execution"""
from samcli.hook_packages.terraform.hooks.prepare.types import ResourceProperties

INTERNAL_PREFIX = "Internal::"
INTERNAL_API_GATEWAY_INTEGRATION = f"{INTERNAL_PREFIX}ApiGateway::Method::Integration"
INTERNAL_API_GATEWAY_INTEGRATION_RESPONSE = f"{INTERNAL_PREFIX}ApiGateway::Method::Integration::Response"


# TODO(mladan): Add a mechanism for gating internal resources from being added to the metadata file
class InternalApiGatewayIntegrationProperties(ResourceProperties):
    """
    Collect resource properties for translating and linking an aws_api_gateway_integration
    to the AWS::ApiGateway::Method resource
    """

    def __init__(self):
        super(InternalApiGatewayIntegrationProperties, self).__init__()


class InternalApiGatewayIntegrationResponseProperties(ResourceProperties):
    """
    Collect resource properties for translating and linking an aws_api_gateway_integration_response
    to the AWS::ApiGateway::Method resource
    """

    def __init__(self):
        super(InternalApiGatewayIntegrationResponseProperties, self).__init__()
