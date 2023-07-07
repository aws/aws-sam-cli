"""
Module for API Gateway-related Terraform translation logic
"""

import logging
from typing import Dict, List, Optional

from samcli.hook_packages.terraform.hooks.prepare.exceptions import OpenAPIBodyNotSupportedException
from samcli.hook_packages.terraform.hooks.prepare.types import (
    References,
    ResourceProperties,
    ResourceTranslationValidator,
    TFResource,
)

LOG = logging.getLogger(__name__)

INVOKE_ARN_FORMAT = (
    "arn:${{AWS::Partition}}:apigateway:${{AWS::Region}}:"
    "lambda:path/2015-03-31/functions/${{{function_logical_id}.Arn}}/invocations"
)

INTEGRATION_PROPERTIES = [
    "Uri",
    "Type",
    "ContentHandling",
    "ConnectionType",
]


class RESTAPITranslationValidator(ResourceTranslationValidator):
    def validate(self):
        """
        Validation function to check if the API Gateway REST API resource can be
        translated and used by AWS SAM CLI

        Raises
        -------
        OpenAPIBodyNotSupportedException if the given api_gateway_rest_api resource contains
            an OpenAPI spec with a reference to a computed value not parsable by AWS SAM CLI
        """
        if _unsupported_reference_field("body", self.resource, self.config_resource):
            raise OpenAPIBodyNotSupportedException(self.config_resource.full_address)


def _unsupported_reference_field(field: str, resource: Dict, config_resource: TFResource) -> bool:
    """
    Check if a field in a resource is a reference to a computed value that is unknown until
    apply-time. These fields are not visible to AWS SAM CLI until the Terraform application
    is applied, meaning that the field isn't parsable by `sam local` commands and isn't supported
    with the current hook implementation.

    Parameters
    ----------
    field: str
        String representation of the field to looks for
    resource: Dict
        Dict containing the resource properties to look in
    config_resource
        The configuration resource that will contain possible references

    Returns
    -------
    bool
        True if the resource contains an field with a reference not parsable by AWS SAM CLI,
        False otherwise
    """
    return bool(
        not (resource.get(field) or resource.get("values", {}).get(field))
        and config_resource.attributes.get(field)
        and isinstance(config_resource.attributes.get(field), References)
    )


class ApiGatewayResourceProperties(ResourceProperties):
    """
    contains the collection logic of the required properties for linking the aws_api_gateway_resource resources.
    """

    def __init__(self):
        super(ApiGatewayResourceProperties, self).__init__()


class ApiGatewayMethodProperties(ResourceProperties):
    """
    contains the collection logic of the required properties for linking the aws_api_gateway_method resources.
    """

    def __init__(self):
        super(ApiGatewayMethodProperties, self).__init__()


class ApiGatewayRestApiProperties(ResourceProperties):
    """
    contains the collection logic of the required properties for linking the aws_api_gateway_rest_api resources.
    """

    def __init__(self):
        super(ApiGatewayRestApiProperties, self).__init__()


class ApiGatewayStageProperties(ResourceProperties):
    """
    Contains the collection logic of the required properties for linking the aws_api_gateway_stage resources.
    """

    def __init__(self):
        super(ApiGatewayStageProperties, self).__init__()


class ApiGatewayAuthorizerProperties(ResourceProperties):
    """
    Contains the collection logic of the required properties for linking the aws_api_gateway_authorizer resources.
    """

    def __init__(self):
        super(ApiGatewayAuthorizerProperties, self).__init__()


def add_integrations_to_methods(
    gateway_methods_cfn: Dict[str, List], gateway_integrations_cfn: Dict[str, List]
) -> None:
    """
    Iterate through all the API Gateway methods in the translated CFN dict. For each API Gateway method,
    search the internal integration resources using the integrations' unique identifier to find the
    one that corresponds with that API Gateway method. Once found, append the properties of the internal
    integration resource to match what CFN expects, which is an 'Integration' property on the API Gateway
    method resource itself.

    E.g.
    AwsApiGatewayMethod:
      Type: AWS::ApiGateway::Method
      Properties:
        Integration:
          Uri: Fn::Sub: arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${function.Arn}/invocations
          Type: AWS_PROXY

    Parameters
    ----------
    gateway_methods_cfn: Dict[str, List]
        Dict containing API Gateway Methods to be mutated with addition integration properties
    gateway_integrations_cfn: Dict[str, List]
        Dict containing Internal API Gateway integrations to be appended to the CFN dict
    """
    for config_address, cfn_dicts in gateway_methods_cfn.items():
        for method_resource in cfn_dicts:
            resource_properties = method_resource.get("Properties", {})
            search_key = _gateway_method_integration_identifier(resource_properties)
            integration_properties = _find_gateway_integration(search_key, gateway_integrations_cfn)
            if not integration_properties:
                LOG.debug("A corresponding gateway integration for the gateway method %s was not found", config_address)
                continue
            _create_gateway_method_integration(method_resource, integration_properties)


def add_integration_responses_to_methods(
    gateway_methods_cfn: Dict[str, List], gateway_integration_responses_cfn: Dict[str, List]
) -> None:
    """
    Iterate through all the API Gateway methods in the translated CFN dict. For each API Gateway method,
    search the internal integration response resources using the responses' unique identifier to find the
    one that corresponds with that API Gateway method. Once found, update the matched Method resource to update its
    integration property to append the properties of the internal integration response resource to its
    IntegrationResponses list.
    E.g.
    AwsApiGatewayMethod:
      Type: AWS::ApiGateway::Method
      Properties:
        Integration:
          Uri: Fn::Sub: arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${function.Arn}/invocations
          IntegrationResponses:
            - ResponseParameters:
                - "method.response.header.X-Some-Header": "integration.response.header.X-Some-Other-Header"
    Parameters
    ----------
    gateway_methods_cfn: Dict[str, List]
        Dict containing API Gateway Methods to be mutated with addition integration properties
    gateway_integration_responses_cfn: Dict[str, List]
        Dict containing Internal API Gateway integration responses to be appended to the CFN dict
    """
    for config_address, cfn_dicts in gateway_methods_cfn.items():
        for method_resource in cfn_dicts:
            method_resource_properties = method_resource.get("Properties", {})
            search_key = _gateway_method_integration_identifier(method_resource_properties)
            integration_response_properties = _find_gateway_integration(search_key, gateway_integration_responses_cfn)
            if not integration_response_properties:
                LOG.debug(
                    "A corresponding gateway integration response for the gateway method %s was not found",
                    config_address,
                )
                continue

            _create_gateway_method_integration_response(method_resource, integration_response_properties)


def _find_gateway_integration(search_key: set, gateway_integrations_cfn: Dict[str, List]) -> Optional[dict]:
    """
    Iterate through all internal API Gateway integration or integration response and search of an
    integration / integration  response whose unique identifier matches the given search key.

    Parameters
    ----------
    search_key: set
        Set containing the unique identifier of the API Gateway integration to match
    gateway_integrations_cfn: Dict[str, List]
        Dict containing all Internal API Gateway integration resources to search through

    Returns
    -------
        Properties of the internal API Gateway integration / integration response if found, otherwise returns None

    """
    for _, gateway_integrations in gateway_integrations_cfn.items():
        for resource in gateway_integrations:
            resource_properties = resource.get("Properties", {})
            integration_key = _gateway_method_integration_identifier(resource_properties)
            if integration_key == search_key:
                return dict(resource_properties)
    return None


def _gateway_method_integration_identifier(resource_properties: dict) -> set:
    """
    Given a dict containing the properties that uniquely identify an
    API Gateway integration (RestApiId, ResourceId, HttpMethod)
    returns a set containing these fields that be used to check for equality of integrations.

    Parameters
    ----------
    resource_properties: dict
        Dict containing the resource properties that can be used to uniquely identify and API Gateway integration

    Returns
    -------
        Returns a set comprised of unique identifiers of an API Gateway integration

    """
    rest_api_id = _get_reference_from_string_or_intrinsic(resource_properties, "RestApiId")
    resource_id = _get_reference_from_string_or_intrinsic(resource_properties, "ResourceId")
    return {
        rest_api_id,
        resource_id,
        resource_properties.get("HttpMethod", ""),
    }


def _get_reference_from_string_or_intrinsic(resource_properties: dict, property_key: str) -> str:
    """
    Check if a reference value is a constant string ARN or if it is a reference to a logical ID.
    Return either the ARN or the logical ID

    Parameters
    ----------
    resource_properties: dict
        Resource properties to search through
    property_key: str
        Property to find

    Returns
    -------
        A string corresponding to the reference of the given field
    """
    return str(
        resource_properties.get(property_key, {}).get("Ref", "")
        if isinstance(resource_properties.get(property_key), dict)
        else resource_properties.get(property_key, "")
    )


def _create_gateway_method_integration(method_resource: dict, integration_resource_properties: dict) -> None:
    """
    Set the relevant resource properties defined in the integration
    internal resource on the API Gateway method resource Integration field

    Parameters
    ----------
    method_resource: dict
        Dict containing the AWS CFN resource for the API Gateway method resource
    integration_resource_properties: dict
        Dict containing the resource properties from the Internal Gateway Integration CFN resource
    """
    method_resource["Properties"]["Integration"] = {}
    for integration_property in INTEGRATION_PROPERTIES:
        property_value = integration_resource_properties.get(integration_property, "")
        if property_value:
            method_resource["Properties"]["Integration"][integration_property] = property_value


def _create_gateway_method_integration_response(
    method_resource: dict, integration_response_resource_properties: dict
) -> None:
    """
    Set the relevant resource properties defined in the integration response internal resource on the API Gateway
    method resource Integration field

    Parameters
    ----------
    method_resource: dict
        Dict containing the AWS CFN resource for the API Gateway method resource
    integration_response_resource_properties: dict
        Dict containing the resource properties from the Internal Gateway Integration Response CFN resource
    """
    integration_resource = method_resource["Properties"].get("Integration", {})
    integration_responses_list = integration_resource.get("IntegrationResponses", [])
    integration_responses_list.append(
        {"ResponseParameters": integration_response_resource_properties.get("ResponseParameters", {})}
    )
    integration_resource["IntegrationResponses"] = integration_responses_list
    method_resource["Properties"]["Integration"] = integration_resource
