"""Class that parses the CloudFormation Api Template"""
import logging
from typing import Type, Dict, Union, List, Optional, Any

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.swagger.reader import SwaggerReader
from samcli.lib.providers.api_collector import ApiCollector

from samcli.lib.providers.provider import Cors, Stack
from samcli.local.apigw.local_apigw_service import Route
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

LOG = logging.getLogger(__name__)


class CfnBaseApiProvider:
    RESOURCE_TYPE = "Type"

    def extract_resources(self, stacks: List[Stack], collector: ApiCollector, cwd: Optional[str] = None) -> None:
        """
        Extract the Route Object from a given resource and adds it to the RouteCollector.

        Parameters
        ----------
        stacks: List[Stack]
            List of stacks apis are extracted from
        collector: samcli.lib.providers.api_collector.ApiCollector
            Instance of the API collector that where we will save the API information
        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file
        """
        raise NotImplementedError("not implemented")

    @staticmethod
    def extract_swagger_route(
        stack_path: str,
        logical_id: str,
        body: Dict,
        uri: Union[str, Dict],
        binary_media: Optional[List],
        collector: ApiCollector,
        cwd: Optional[str] = None,
        event_type: str = Route.API,
    ) -> None:
        """
        Parse the Swagger documents and adds it to the ApiCollector.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        logical_id : str
            Logical ID of the resource
        body : dict
            The body of the RestApi
        uri : str or dict
            The url to location of the RestApi
        binary_media : list
            The link to the binary media
        collector : samcli.lib.providers.api_collector.ApiCollector
            Instance of the Route collector that where we will save the route information
        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file
        event_type : str
            The event type, 'Api' or 'HttpApi', see samcli/local/apigw/local_apigw_service.py:35
        """
        reader = SwaggerReader(definition_body=body, definition_uri=uri, working_dir=cwd)
        swagger = reader.read()
        parser = SwaggerParser(stack_path, swagger)
        routes = parser.get_routes(event_type)
        LOG.debug("Found '%s' APIs in resource '%s'", len(routes), logical_id)

        collector.add_routes(logical_id, routes)

        collector.add_binary_media_types(logical_id, parser.get_binary_media_types())  # Binary media from swagger
        collector.add_binary_media_types(logical_id, binary_media)  # Binary media specified on resource in template

    def extract_cors(self, cors_prop: Union[Dict, str]) -> Optional[Cors]:
        """
        Extract Cors property from AWS::Serverless::Api resource by reading and parsing Swagger documents. The result
        is added to the Api.

        Parameters
        ----------
        cors_prop : dict
            Resource properties for Cors
        """
        cors = None
        if cors_prop and isinstance(cors_prop, dict):
            allow_methods = self._get_cors_prop(cors_prop, "AllowMethods")
            if allow_methods:
                allow_methods = CfnBaseApiProvider.normalize_cors_allow_methods(allow_methods)
            else:
                allow_methods = ",".join(sorted(Route.ANY_HTTP_METHODS))

            allow_origin = self._get_cors_prop(cors_prop, "AllowOrigin")
            allow_headers = self._get_cors_prop(cors_prop, "AllowHeaders")
            allow_credentials = self._get_cors_prop(cors_prop, "AllowCredentials", True)
            max_age = self._get_cors_prop(cors_prop, "MaxAge")

            cors = Cors(
                allow_origin=allow_origin,
                allow_methods=allow_methods,
                allow_headers=allow_headers,
                allow_credentials=allow_credentials,
                max_age=max_age,
            )
        elif cors_prop and isinstance(cors_prop, str):
            allow_origin = cors_prop
            if not (allow_origin.startswith("'") and allow_origin.endswith("'")):
                raise InvalidSamDocumentException(
                    "Cors Properties must be a quoted string " '(i.e. "\'*\'" is correct, but "*" is not).'
                )
            allow_origin = allow_origin.strip("'")

            cors = Cors(
                allow_origin=allow_origin,
                allow_methods=",".join(sorted(Route.ANY_HTTP_METHODS)),
                allow_headers=None,
                allow_credentials=None,
                max_age=None,
            )
        return cors

    @staticmethod
    def _get_cors_prop(cors_dict: Dict, prop_name: str, allow_bool: bool = False) -> Optional[str]:
        """
        Extract cors properties from dictionary and remove extra quotes.

        Parameters
        ----------
        cors_dict : dict
            Resource properties for Cors

        prop_name : str
            Cors property to get the value for

        allow_bool : bool
            If a boolean value is allowed for this property or not (defaults to false)

        Return
        ------
        A string with the extra quotes removed
        """
        prop = cors_dict.get(prop_name)
        if prop:
            if allow_bool and isinstance(prop, bool):
                prop = "'true'"  # We alredy know this is true due to L141 passing
            if not isinstance(prop, str) or prop.startswith("!"):
                LOG.warning(
                    "CORS Property %s was not fully resolved. Will proceed as if the Property was not defined.",
                    prop_name,
                )
                return None

            if not (prop.startswith("'") and prop.endswith("'")):
                raise InvalidSamDocumentException(
                    "{} must be a quoted string " '(i.e. "\'value\'" is correct, but "value" is not).'.format(prop_name)
                )
            prop = prop.strip("'")
        return prop

    def extract_cors_http(
        self,
        cors_prop: Union[bool, Dict],
    ) -> Optional[Cors]:
        """
        Extract Cors property from AWS::Serverless::HttpApi resource by reading and parsing Swagger documents.
        The result is added to the HttpApi.

        Parameters
        ----------
        cors_prop : dict
            Resource properties for CorsConfiguration
        """
        cors = None
        if cors_prop and isinstance(cors_prop, dict):
            allow_methods = self._get_cors_prop_http(cors_prop, "AllowMethods", list)
            if isinstance(allow_methods, list):
                allow_methods = CfnBaseApiProvider.normalize_cors_allow_methods(allow_methods)
            else:
                allow_methods = ",".join(sorted(Route.ANY_HTTP_METHODS))

            allow_origins = self._get_cors_prop_http(cors_prop, "AllowOrigins", list)
            if isinstance(allow_origins, list):
                allow_origins = ",".join(allow_origins)
            allow_headers = self._get_cors_prop_http(cors_prop, "AllowHeaders", list)
            if isinstance(allow_headers, list):
                allow_headers = ",".join(allow_headers)

            # Read AllowCredentials but only output the header with the case-sensitive value of true
            # (see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Allow-Credentials)
            allow_credentials = "true" if self._get_cors_prop_http(cors_prop, "AllowCredentials", bool) else None

            max_age = self._get_cors_prop_http(cors_prop, "MaxAge", int)

            cors = Cors(
                allow_origin=allow_origins,
                allow_methods=allow_methods,
                allow_headers=allow_headers,
                allow_credentials=allow_credentials,
                max_age=max_age,
            )
        elif cors_prop and isinstance(cors_prop, bool) and cors_prop:
            cors = Cors(
                allow_origin="*",
                allow_methods=",".join(sorted(Route.ANY_HTTP_METHODS)),
                allow_headers=None,
                allow_credentials=None,
                max_age=None,
            )
        return cors

    @staticmethod
    def _get_cors_prop_http(
        cors_dict: Dict,
        prop_name: str,
        expect_type: Type,
    ) -> Optional[Any]:
        """
        Extract cors properties from dictionary.

        Parameters
        ----------
        cors_dict : dict
            Resource properties for Cors
        prop_name : str
            Property name
        expect_type : type
            Expect property type

        Return
        ------
        Value with matching type
        """
        prop = cors_dict.get(prop_name)
        if prop:
            if not isinstance(prop, expect_type):
                LOG.warning(
                    "CORS Property %s was not fully resolved. Will proceed as if the Property was not defined.",
                    prop_name,
                )
                return None
        return prop

    @staticmethod
    def normalize_cors_allow_methods(allow_methods: Union[str, List[str]]) -> str:
        """
        Normalize cors AllowMethods and Options to the methods if it's missing.

        Parameters
        ----------
        allow_methods : str
            The allow_methods string provided in the query

        Return
        -------
        A string with normalized route
        """
        if allow_methods == "*" or (isinstance(allow_methods, list) and "*" in allow_methods):
            return ",".join(sorted(Route.ANY_HTTP_METHODS))
        if isinstance(allow_methods, list):
            methods = allow_methods
        else:
            methods = allow_methods.split(",")
        normalized_methods = []
        for method in methods:
            normalized_method = method.strip().upper()
            if normalized_method not in Route.ANY_HTTP_METHODS:
                raise InvalidSamDocumentException("The method {} is not a valid CORS method".format(normalized_method))
            normalized_methods.append(normalized_method)

        if "OPTIONS" not in normalized_methods:
            normalized_methods.append("OPTIONS")

        return ",".join(sorted(normalized_methods))
