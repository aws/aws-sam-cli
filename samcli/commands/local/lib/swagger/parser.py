"""Handles Swagger Parsing"""

import logging
from typing import List, Union, Dict

from samcli.commands.local.lib.swagger.integration_uri import LambdaUri, IntegrationType
from samcli.local.apigw.local_apigw_service import Route, LambdaAuthorizer, Authorizer
from samcli.local.apigw.exceptions import (
    MultipleAuthorizerException,
    IncorrectOasWithDefaultAuthorizerException,
    InvalidOasVersion,
    InvalidSecurityDefinition,
)

LOG = logging.getLogger(__name__)


class SwaggerParser:
    _AUTHORIZER_KEY = "x-amazon-apigateway-authorizer"
    _AUTH_KEY = "x-amazon-apigateway-auth"
    _INTEGRATION_KEY = "x-amazon-apigateway-integration"
    _ANY_METHOD_EXTENSION_KEY = "x-amazon-apigateway-any-method"
    _BINARY_MEDIA_TYPES_EXTENSION_KEY = "x-amazon-apigateway-binary-media-types"  # pylint: disable=C0103
    _ANY_METHOD = "ANY"

    def __init__(self, stack_path: str, swagger):
        """
        Constructs an Swagger Parser object

        :param str stack_path: Path of the stack the resource is located
        :param dict swagger: Dictionary representation of a Swagger document
        """
        self.swagger = swagger or {}
        self.stack_path = stack_path

    def get_binary_media_types(self):
        """
        Get the list of Binary Media Types from Swagger

        Returns
        -------
        list of str
            List of strings that represent the Binary Media Types for the API, defaulting to empty list is None

        """
        return self.swagger.get(self._BINARY_MEDIA_TYPES_EXTENSION_KEY) or []

    def get_authorizers(self) -> Dict[str, Authorizer]:
        """
        Parse Swagger document and returns a list of Authorizer objects

        Returns
        -------
        dict[str, Authorizer]
            A map of authorizer names and Authorizer objects found in the body definition
        """
        authorizers: Dict[str, Authorizer] = {}

        authorizer_dict = {}
        document_version = self.swagger.get("swagger") or self.swagger.get("openapi") or ""

        if document_version.startswith("2."):
            LOG.debug("Parsing Swagger document using 2.0 specification")
            authorizer_dict = self.swagger.get("securityDefinitions", {})
        elif document_version.startswith("3."):
            LOG.debug("Parsing Swagger document using 3.0 specification")
            authorizer_dict = self.swagger.get("components", {}).get("securitySchemes", {})
        else:
            raise InvalidOasVersion(
                f"An invalid OpenApi version was detected: '{document_version}', must be one of 2.x or 3.x",
            )

        for auth_name, properties in authorizer_dict.items():
            authorizer_object = properties.get(self._AUTHORIZER_KEY)

            if authorizer_object:
                valid_types = ["token", "request"]

                authorizer_type = authorizer_object.get("type", "").lower()
                payload_version = authorizer_object.get("authorizerPayloadFormatVersion", "1.0")

                lambda_name = LambdaUri.get_function_name(authorizer_object.get("authorizerUri"))

                if not lambda_name:
                    LOG.warning(
                        "Unable to parse authorizerUri '%s' for authorizer '%s', skipping", lambda_name, auth_name
                    )

                    continue

                # only add authorizer if it is token or request based (not jwt)
                if authorizer_type in valid_types and lambda_name:
                    lambda_authorizer = LambdaAuthorizer(
                        authorizer_name=auth_name,
                        type=authorizer_type,
                        payload_version=payload_version,
                        lambda_name=lambda_name,
                        identity_sources=[authorizer_object.get("identitySource")],
                        validation_string=authorizer_object.get("identityValidationExpression"),
                    )

                    authorizers[auth_name] = lambda_authorizer
                else:
                    LOG.info("Lambda authorizer '%s' type '%s' is unsupported, skipping", auth_name, authorizer_type)
            else:
                LOG.info("Skip parsing unsupported authorizer %s", auth_name)

        return authorizers

    def get_default_authorizer(self, event_type: str) -> Union[str, None]:
        """
        Parses the body definition to find root level Authorizer definitions

        Parameters
        ----------
        event_type: str
            String representing the type of API the definition body is defined as

        Returns
        -------
        Union[str, None]
            Returns the name of the authorizer, if there is one defined, otherwise None
        """
        document_version = self.swagger.get("swagger") or self.swagger.get("openapi") or ""
        authorizers = self.swagger.get("security", [])

        if document_version.startswith("3.") and event_type == Route.HTTP:
            if len(authorizers) > 1:
                raise MultipleAuthorizerException(
                    f"There must only be a single authorizer defined for a single route, found '{len(authorizers)}'"
                )

            if len(authorizers) == 1:
                auth_name = str(list(authorizers[0])[0])

                LOG.debug("Found default authorizer: %s", auth_name)

                return auth_name

        if authorizers:
            raise IncorrectOasWithDefaultAuthorizerException(
                "Root level definition of default authorizers are only supported for OpenApi 3.0"
            )

        return None

    def get_routes(self, event_type=Route.API) -> List[Route]:
        """
        Parses a swagger document and returns a list of APIs configured in the document.

        Swagger documents have the following structure
        {
            "/path1": {    # path
                "get": {   # method
                    "x-amazon-apigateway-integration": {   # integration
                        "type": "aws_proxy",

                        # URI contains the Lambda function ARN that needs to be parsed to get Function Name
                        "uri": {
                            "Fn::Sub":
                                "arn:aws:apigateway:aws:lambda:path/2015-03-31/functions/${LambdaFunction.Arn}/..."
                        }
                    }
                },
                "post": {
                },
            },
            "/path2": {
                ...
            }
        }

        Returns
        -------
        list of list of samcli.commands.local.apigw.local_apigw_service.Route
            List of APIs that are configured in the Swagger document
        """

        result = []
        paths_dict = self.swagger.get("paths", {})

        for full_path, path_config in paths_dict.items():
            for method, method_config in path_config.items():
                function_name = self._get_integration_function_name(method_config)
                if not function_name:
                    LOG.debug(
                        "Lambda function integration not found in Swagger document at path='%s' method='%s'",
                        full_path,
                        method,
                    )
                    continue

                if method.lower() == self._ANY_METHOD_EXTENSION_KEY:
                    # Convert to a more commonly used method notation
                    method = self._ANY_METHOD

                payload_format_version = self._get_payload_format_version(method_config)

                authorizers = method_config.get("security", None)
                authorizer = None

                if authorizers is None:
                    # user has no security defined, set blank to use default
                    authorizer = ""
                else:
                    if not isinstance(authorizers, list):
                        raise InvalidSecurityDefinition(
                            "Invalid security definition found, authorizers for "
                            f"path='{full_path}' method='{method}' must be a list"
                        )

                    if len(authorizers) > 1:
                        raise MultipleAuthorizerException(
                            "There must only be a single authorizer defined "
                            f"for path='{full_path}' method='{method}', found '{len(authorizers)}'"
                        )

                    if len(authorizers) == 1:
                        # user has authorizer defined
                        authorizer = str(list(authorizers[0])[0])

                route = Route(
                    function_name,
                    full_path,
                    methods=[method],
                    event_type=event_type,
                    payload_format_version=payload_format_version,
                    operation_name=method_config.get("operationId"),
                    stack_path=self.stack_path,
                    authorizer_name=authorizer,
                )
                result.append(route)

        return result

    def _get_integration(self, method_config):
        """
        Get Integration defined in the method configuration.
        Integration configuration is defined under the special "x-amazon-apigateway-integration" key. We care only
        about Lambda integrations, which are of type aws_proxy, and ignore the rest.

        Parameters
        ----------
        method_config : dict
            Dictionary containing the method configuration which might contain integration settings

        Returns
        -------
        dict or None
            integration, if possible. None, if not.
        """
        if not isinstance(method_config, dict) or self._INTEGRATION_KEY not in method_config:
            return None

        integration = method_config[self._INTEGRATION_KEY]

        if (
            integration
            and isinstance(integration, dict)
            and integration.get("type").lower() == IntegrationType.aws_proxy.value
        ):
            # Integration must be "aws_proxy" otherwise we don't care about it
            return integration

        return None

    def _get_integration_function_name(self, method_config):
        """
        Tries to parse the Lambda Function name from the Integration defined in the method configuration.
        Integration configuration is defined under the special "x-amazon-apigateway-integration" key. We care only
        about Lambda integrations, which are of type aws_proxy, and ignore the rest. Integration URI is complex and
        hard to parse. Hence we do our best to extract function name out of integration URI. If not possible, we
        return None.

        Parameters
        ----------
        method_config : dict
            Dictionary containing the method configuration which might contain integration settings

        Returns
        -------
        string or None
            Lambda function name, if possible. None, if not.
        """
        integration = self._get_integration(method_config)
        if integration is None:
            return None

        return LambdaUri.get_function_name(integration.get("uri"))

    def _get_payload_format_version(self, method_config):
        """
        Get the "payloadFormatVersion" from the Integration defined in the method configuration.

        Parameters
        ----------
        method_config : dict
            Dictionary containing the method configuration which might contain integration settings

        Returns
        -------
        string or None
            Payload format version, if exists. None, if not.
        """
        integration = self._get_integration(method_config)
        if integration is None:
            return None

        return integration.get("payloadFormatVersion")
