"""
Module for API Gateway-related Terraform translation logic
"""

from typing import Dict

from samcli.hook_packages.terraform.hooks.prepare.exceptions import OpenAPIBodyNotSupportedException
from samcli.hook_packages.terraform.hooks.prepare.types import (
    References,
    ResourceProperties,
    ResourceTranslationValidator,
    TFResource,
)


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
