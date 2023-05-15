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
from samcli.lib.utils.resources import AWS_APIGATEWAY_METHOD

LOG = logging.getLogger(__name__)

INVOKE_ARN_FORMAT = (
    "arn:aws:apigateway:${{AWS::Region}}:lambda:path/2015-03-31/functions/${{{function_logical_id}.Arn}}/invocations"
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
        not resource.get(field)
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


def add_integrations_to_methods(cfn_dict: dict, gateway_integrations_cfn: Dict[str, List]) -> None:
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
    cfn_dict: dict
        Resultant CFN dict that will be mutated to append integrations to each API Gateway method
    gateway_integrations_cfn: Dict[str, List]
        Dict containing Internal API Gateway integrations to be appended to the CFN dict
    """
    for logical_id, resource in cfn_dict.get("Resources").items():
        if resource.get("Type", "") == AWS_APIGATEWAY_METHOD:
            resource_properties = resource.get("Properties", {})
            search_key = _gateway_method_integration_identifier(resource_properties)
            integration_properties = _find_gateway_integration(search_key, gateway_integrations_cfn)
            if not integration_properties:
                LOG.debug("A corresponding gateway integration for the gateway method %s was not found", logical_id)
                continue
            _create_gateway_method_integration(resource, integration_properties)


def _find_gateway_integration(search_key: set, gateway_integrations_cfn: Dict[str, List]) -> Optional[dict]:
    """
    Iterate through all internal API Gateway integrations and search of an
    integration whose unique identifier matches the given search key.

    Parameters
    ----------
    search_key: set
        Set containing the unique identifier of the API Gateway integration to match
    gateway_integrations_cfn: Dict[str, List]
        Dict containing all Internal API Gateway integration resources to search through

    Returns
    -------
        Properties of the internal API Gateway integration if found, otherwise returns None

    """
    for _, gateway_integrations in gateway_integrations_cfn.items():
        for resource in gateway_integrations:
            resource_properties = resource.get("Properties", {})
            integration_key = _gateway_method_integration_identifier(resource_properties)
            if integration_key == search_key:
                return resource_properties
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
    return {
        resource_properties.get("RestApiId", {}).get("Ref", ""),
        resource_properties.get("ResourceId", {}).get("Ref", ""),
        resource_properties.get("HttpMethod", ""),
    }


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
