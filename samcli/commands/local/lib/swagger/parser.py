"""Handles Swagger Parsing"""

import logging

from samcli.commands.local.lib.swagger.integration_uri import LambdaUri, IntegrationType
from samcli.local.apigw.local_apigw_service import Route

LOG = logging.getLogger(__name__)


class SwaggerParser:
    _INTEGRATION_KEY = "x-amazon-apigateway-integration"
    _ANY_METHOD_EXTENSION_KEY = "x-amazon-apigateway-any-method"
    _BINARY_MEDIA_TYPES_EXTENSION_KEY = "x-amazon-apigateway-binary-media-types"  # pylint: disable=C0103
    _ANY_METHOD = "ANY"

    def __init__(self, swagger):
        """
        Constructs an Swagger Parser object

        :param dict swagger: Dictionary representation of a Swagger document
        """
        self.swagger = swagger or {}

    def get_binary_media_types(self):
        """
        Get the list of Binary Media Types from Swagger

        Returns
        -------
        list of str
            List of strings that represent the Binary Media Types for the API, defaulting to empty list is None

        """
        return self.swagger.get(self._BINARY_MEDIA_TYPES_EXTENSION_KEY) or []

    def get_routes(self):
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
                route = Route(function_name, full_path, methods=[method])
                result.append(route)
        return result

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
        if not isinstance(method_config, dict) or self._INTEGRATION_KEY not in method_config:
            return None

        integration = method_config[self._INTEGRATION_KEY]

        if integration and isinstance(integration, dict) and integration.get("type") == IntegrationType.aws_proxy.value:
            # Integration must be "aws_proxy" otherwise we don't care about it
            return LambdaUri.get_function_name(integration.get("uri"))

        return None
