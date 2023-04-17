"""Parses SAM given the template"""

import logging
from typing import Dict, List, Optional, Tuple, Union, cast

from samcli.commands.local.lib.swagger.integration_uri import LambdaUri
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.providers.api_collector import ApiCollector
from samcli.lib.providers.cfn_base_api_provider import CfnBaseApiProvider
from samcli.lib.providers.provider import Stack
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.resources import AWS_SERVERLESS_API, AWS_SERVERLESS_FUNCTION, AWS_SERVERLESS_HTTPAPI
from samcli.local.apigw.authorizers.authorizer import Authorizer
from samcli.local.apigw.authorizers.lambda_authorizer import LambdaAuthorizer
from samcli.local.apigw.route import Route

LOG = logging.getLogger(__name__)


class SamApiProvider(CfnBaseApiProvider):
    TYPES = [AWS_SERVERLESS_FUNCTION, AWS_SERVERLESS_API, AWS_SERVERLESS_HTTPAPI]
    _EVENT_TYPE_API = "Api"
    _EVENT_TYPE_HTTP_API = "HttpApi"
    _FUNCTION_EVENT = "Events"
    _EVENT_PATH = "Path"
    _EVENT_METHOD = "Method"
    _EVENT_TYPE = "Type"
    IMPLICIT_API_RESOURCE_ID = "ServerlessRestApi"
    IMPLICIT_HTTP_API_RESOURCE_ID = "ServerlessHttpApi"

    _AUTH = "Auth"
    _AUTH_HEADER = "Header"
    _AUTH_SIMPLE_RESPONSES = "EnableSimpleResponses"
    _AUTHORIZER = "Authorizer"
    _AUTHORIZERS = "Authorizers"
    _DEFAULT_AUTHORIZER = "DefaultAuthorizer"
    _FUNCTION_TYPE = "FunctionPayloadType"
    _AUTHORIZER_PAYLOAD = "AuthorizerPayloadFormatVersion"
    _FUNCTION_ARN = "FunctionArn"
    _VALIDATION_EXPRESSION = "ValidationExpression"
    _IDENTITY = "Identity"
    _IDENTITY_QUERY = "QueryStrings"
    _IDENTITY_HEADERS = "Headers"
    _IDENTITY_CONTEXT = "Context"
    _IDENTITY_STAGE = "StageVariables"
    _API_IDENTITY_SOURCE_PREFIX = "method."
    _HTTP_IDENTITY_SOURCE_PREFIX = "$"

    def extract_resources(self, stacks: List[Stack], collector: ApiCollector, cwd: Optional[str] = None) -> None:
        """
        Extract the Route Object from a given resource and adds it to the RouteCollector.

        Parameters
        ----------
        stacks: List[Stack]
            List of stacks apis are extracted from
        collector: samcli.commands.local.lib.route_collector.ApiCollector
            Instance of the API collector that where we will save the API information
        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file
        """
        # AWS::Serverless::Function is currently included when parsing of Apis because when SamBaseProvider is run on
        # the template we are creating the implicit apis due to plugins that translate it in the SAM repo,
        # which we later merge with the explicit ones in SamApiProvider.merge_apis. This requires the code to be
        # parsed here and in InvokeContext.
        for stack in stacks:
            for logical_id, resource in stack.resources.items():
                resource_type = resource.get(CfnBaseApiProvider.RESOURCE_TYPE)
                if resource_type == AWS_SERVERLESS_FUNCTION:
                    self._extract_routes_from_function(stack.stack_path, logical_id, resource, collector)
                if resource_type == AWS_SERVERLESS_API:
                    self._extract_from_serverless_api(stack.stack_path, logical_id, resource, collector, cwd=cwd)
                if resource_type == AWS_SERVERLESS_HTTPAPI:
                    self._extract_from_serverless_http(stack.stack_path, logical_id, resource, collector, cwd=cwd)

        collector.routes = self.merge_routes(collector)

    def _extract_from_serverless_api(
        self, stack_path: str, logical_id: str, api_resource: Dict, collector: ApiCollector, cwd: Optional[str] = None
    ) -> None:
        """
        Extract APIs from AWS::Serverless::Api resource by reading and parsing Swagger documents. The result is added
        to the collector.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        logical_id : str
            Logical ID of the resource

        api_resource : dict
            Resource definition, including its properties

        collector: samcli.lib.providers.api_collector.ApiCollector
            Instance of the API collector that where we will save the API information

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        """

        properties = api_resource.get("Properties", {})
        body = properties.get("DefinitionBody")
        uri = properties.get("DefinitionUri")
        binary_media = properties.get("BinaryMediaTypes", [])
        cors = self.extract_cors(properties.get("Cors", {}))
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")
        if not body and not uri:
            # Swagger is not found anywhere.
            LOG.debug(
                "Skipping resource '%s'. Swagger document not found in DefinitionBody and DefinitionUri", logical_id
            )
            return
        CfnBaseApiProvider.extract_swagger_route(stack_path, logical_id, body, uri, binary_media, collector, cwd=cwd)
        collector.stage_name = stage_name
        collector.stage_variables = stage_variables
        collector.cors = cors

        auth = properties.get(SamApiProvider._AUTH, {})
        if not auth:
            return

        default_authorizer = auth.get(SamApiProvider._DEFAULT_AUTHORIZER)
        if default_authorizer:
            collector.set_default_authorizer(logical_id, default_authorizer)

        self._extract_authorizers_from_props(logical_id, auth, collector, Route.API)

    @staticmethod
    def _extract_request_lambda_authorizer(
        auth_name: str, function_name: str, prefix: str, properties: dict, event_type: str
    ) -> LambdaAuthorizer:
        """
        Generates a request Lambda Authorizer from the given identity object

        Parameters
        ----------
        auth_name: str
            Name of the authorizer
        function_name: str
            Name of the Lambda function this authorizer uses
        prefix: str
            The prefix to prepend to identity sources
        properties: dict
            The authorizer properties that contains identity sources and authorizer specific properties
        event_type: str
            The type of API this is (API or HTTP API)

        Returns
        -------
        LambdaAuthorizer
            The request based Lambda Authorizer object
        """
        payload_version = properties.get(SamApiProvider._AUTHORIZER_PAYLOAD)

        if payload_version is not None and not isinstance(payload_version, str):
            raise InvalidSamDocumentException(
                f"'{SamApiProvider._AUTHORIZER_PAYLOAD}' must be of type string for Lambda Authorizer '{auth_name}'."
            )

        if payload_version not in LambdaAuthorizer.PAYLOAD_VERSIONS and event_type == Route.HTTP:
            raise InvalidSamDocumentException(
                f"Lambda Authorizer '{auth_name}' must contain a valid "
                f"'{SamApiProvider._AUTHORIZER_PAYLOAD}' for HTTP APIs."
            )

        simple_responses = properties.get(SamApiProvider._AUTH_SIMPLE_RESPONSES, False)
        if simple_responses and payload_version == LambdaAuthorizer.PAYLOAD_V1:
            raise InvalidSamDocumentException(
                f"{SamApiProvider._AUTH_SIMPLE_RESPONSES} must be used with the 2.0 "
                f"payload format version in Lambda Authorizer '{auth_name}'."
            )

        identity_sources = []
        identity_object = properties.get(SamApiProvider._IDENTITY, {})

        for query_string in identity_object.get(SamApiProvider._IDENTITY_QUERY, []):
            identity_sources.append(f"{prefix}request.querystring.{query_string}")

        for header in identity_object.get(SamApiProvider._IDENTITY_HEADERS, []):
            identity_sources.append(f"{prefix}request.header.{header}")

        # context and stageVariables do not have "method." for V1 APIGW
        # but the V2 still expects "$"
        prefix = SamApiProvider._HTTP_IDENTITY_SOURCE_PREFIX if event_type == Route.HTTP else ""

        for context in identity_object.get(SamApiProvider._IDENTITY_CONTEXT, []):
            identity_sources.append(f"{prefix}context.{context}")

        for stage_variable in identity_object.get(SamApiProvider._IDENTITY_STAGE, []):
            identity_sources.append(f"{prefix}stageVariables.{stage_variable}")

        return LambdaAuthorizer(
            payload_version=payload_version if payload_version else "1.0",
            authorizer_name=auth_name,
            type=LambdaAuthorizer.REQUEST,
            lambda_name=function_name,
            identity_sources=identity_sources,
            use_simple_response=simple_responses,
        )

    @staticmethod
    def _extract_token_lambda_authorizer(
        auth_name: str, function_name: str, prefix: str, identity_object: dict
    ) -> LambdaAuthorizer:
        """
        Generates a token Lambda Authorizer from the given identity object

        Parameters
        ----------
        auth_name: str
            Name of the authorizer
        function_name: str
            Name of the Lambda function this authorizer uses
        prefix: str
            The prefix to prepend to identity sources
        identity_object: dict
            The identity source object that contains the various identity sources

        Returns
        -------
        LambdaAuthorizer
            The token based Lambda Authorizer object
        """
        validation_expression = identity_object.get(SamApiProvider._VALIDATION_EXPRESSION)

        header = identity_object.get(SamApiProvider._AUTH_HEADER, "Authorization")
        header = f"{prefix}request.header.{header}"

        return LambdaAuthorizer(
            payload_version=LambdaAuthorizer.PAYLOAD_V1,
            authorizer_name=auth_name,
            type=LambdaAuthorizer.TOKEN,
            lambda_name=function_name,
            identity_sources=[header],
            validation_string=validation_expression,
        )

    @staticmethod
    def _extract_authorizers_from_props(logical_id: str, auth: dict, collector: ApiCollector, event_type: str) -> None:
        """
        Extracts Authorizers from the Auth properties section of Serverless resources

        Parameters
        ----------
        logical_id: str
            The logical ID of the Serverless resource
        auth: dict
            The Auth property dictionary
        collector: ApiCollector
            The Api Collector to send the Authorizers to
        event_type: str
            What kind of API this is (API, HTTP API)
        """
        prefix = (
            SamApiProvider._API_IDENTITY_SOURCE_PREFIX
            if event_type == Route.API
            else SamApiProvider._HTTP_IDENTITY_SOURCE_PREFIX
        )

        authorizers: Dict[str, Authorizer] = {}

        for auth_name, auth_props in auth.get(SamApiProvider._AUTHORIZERS, {}).items():
            authorizer_type = auth_props.get(SamApiProvider._FUNCTION_TYPE, LambdaAuthorizer.TOKEN)
            identity_object = auth_props.get(SamApiProvider._IDENTITY, {})

            function_arn = auth_props.get(SamApiProvider._FUNCTION_ARN)

            if not function_arn:
                LOG.debug("Authorizer '%s' is currently unsupported (must be a Lambda Authorizer), skipping", auth_name)
                continue

            function_name = LambdaUri.get_function_name(function_arn)

            if not function_name:
                LOG.warning("Unable to parse the Lambda ARN for Authorizer '%s', skipping", auth_name)
                continue

            if authorizer_type == LambdaAuthorizer.REQUEST.upper() or event_type == Route.HTTP:
                authorizers[auth_name] = SamApiProvider._extract_request_lambda_authorizer(
                    auth_name, function_name, prefix, auth_props, event_type
                )
            elif authorizer_type == LambdaAuthorizer.TOKEN.upper():
                authorizers[auth_name] = SamApiProvider._extract_token_lambda_authorizer(
                    auth_name, function_name, prefix, identity_object
                )
            else:
                LOG.debug(
                    "Authorizer '%s' is currently unsupported (not of type TOKEN or REQUEST), skipping", auth_name
                )

        collector.add_authorizers(logical_id, authorizers)

    def _extract_from_serverless_http(
        self, stack_path: str, logical_id: str, api_resource: Dict, collector: ApiCollector, cwd: Optional[str] = None
    ) -> None:
        """
        Extract APIs from AWS::Serverless::HttpApi resource by reading and parsing Swagger documents.
        The result is added to the collector.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        logical_id : str
            Logical ID of the resource

        api_resource : dict
            Resource definition, including its properties

        collector: samcli.lib.providers.api_collector.ApiCollector
            Instance of the API collector that where we will save the API information

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        """

        properties = api_resource.get("Properties", {})
        body = properties.get("DefinitionBody")
        uri = properties.get("DefinitionUri")
        cors = self.extract_cors_http(properties.get("CorsConfiguration", {}))
        stage_name = properties.get("StageName")
        stage_variables = properties.get("StageVariables")
        if not body and not uri:
            # Swagger is not found anywhere.
            LOG.debug(
                "Skipping resource '%s'. Swagger document not found in DefinitionBody and DefinitionUri", logical_id
            )
            return
        CfnBaseApiProvider.extract_swagger_route(
            stack_path, logical_id, body, uri, None, collector, cwd=cwd, event_type=Route.HTTP
        )
        collector.stage_name = stage_name
        collector.stage_variables = stage_variables
        collector.cors = cors

        auth = properties.get(SamApiProvider._AUTH, {})
        if not auth:
            return

        default_authorizer = auth.get(SamApiProvider._DEFAULT_AUTHORIZER)
        if default_authorizer:
            collector.set_default_authorizer(logical_id, default_authorizer)

        self._extract_authorizers_from_props(logical_id, auth, collector, Route.HTTP)

    def _extract_routes_from_function(
        self, stack_path: str, logical_id: str, function_resource: Dict, collector: ApiCollector
    ) -> None:
        """
        Fetches a list of routes configured for this SAM Function resource.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        logical_id : str
            Logical ID of the resource

        function_resource : dict
            Contents of the function resource including its properties

        collector: samcli.lib.providers.api_collector.ApiCollector
            Instance of the API collector that where we will save the API information
        """

        resource_properties = function_resource.get("Properties", {})
        serverless_function_events = resource_properties.get(self._FUNCTION_EVENT, {})
        self.extract_routes_from_events(stack_path, logical_id, serverless_function_events, collector)

    def extract_routes_from_events(
        self, stack_path: str, function_logical_id: str, serverless_function_events: Dict, collector: ApiCollector
    ) -> None:
        """
        Given an AWS::Serverless::Function Event Dictionary, extract out all 'route' events and store  within the
        collector

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        function_logical_id : str
            LogicalId of the AWS::Serverless::Function

        serverless_function_events : dict
            Event Dictionary of a AWS::Serverless::Function

        collector: samcli.lib.providers.api_collector.ApiCollector
            Instance of the Route collector that where we will save the route information
        """
        count = 0
        for _, event in serverless_function_events.items():
            event_type = event.get(self._EVENT_TYPE)
            if event_type in [self._EVENT_TYPE_API, self._EVENT_TYPE_HTTP_API]:
                route_resource_id, route = self._convert_event_route(
                    stack_path, function_logical_id, event.get("Properties"), event.get(SamApiProvider._EVENT_TYPE)
                )
                collector.add_routes(route_resource_id, [route])
                count += 1

        LOG.debug("Found '%d' API Events in Serverless function with name '%s'", count, function_logical_id)

    @staticmethod
    def _convert_event_route(
        stack_path: str, lambda_logical_id: str, event_properties: Dict, event_type: str
    ) -> Tuple[str, Route]:
        """
        Converts a AWS::Serverless::Function's Event Property to an Route configuration usable by the provider.

        :param str stack_path: Path of the stack the resource is located
        :param str lambda_logical_id: Logical Id of the AWS::Serverless::Function
        :param dict event_properties: Dictionary of the Event's Property
        :param event_type: The event type, 'Api' or 'HttpApi', see samcli/local/apigw/local_apigw_service.py:35
        :return tuple: tuple of route resource name and route
        """
        path = cast(str, event_properties.get(SamApiProvider._EVENT_PATH))
        method = cast(str, event_properties.get(SamApiProvider._EVENT_METHOD))

        # An RESTAPI (HTTPAPI) Event, can have RestApiId (ApiId) property which designates the resource that owns this
        # API. If omitted, the API is owned by Implicit API resource. This could either be a direct resource logical ID
        # or a "Ref" of the logicalID

        api_resource_id: Union[str, Dict]
        payload_format_version: Optional[str] = None

        if event_type == SamApiProvider._EVENT_TYPE_API:
            api_resource_id = event_properties.get("RestApiId", SamApiProvider.IMPLICIT_API_RESOURCE_ID)
        else:
            api_resource_id = event_properties.get("ApiId", SamApiProvider.IMPLICIT_HTTP_API_RESOURCE_ID)
            payload_format_version = event_properties.get("PayloadFormatVersion")

        if isinstance(api_resource_id, dict) and "Ref" in api_resource_id:
            api_resource_id = api_resource_id["Ref"]

        # This is still a dictionary. Something wrong with the template
        if isinstance(api_resource_id, dict):
            LOG.debug("Invalid RestApiId property of event %s", event_properties)
            raise InvalidSamDocumentException(
                "RestApiId property of resource with logicalId '{}' is invalid. "
                "It should either be a LogicalId string or a Ref of a Logical Id string".format(lambda_logical_id)
            )

        use_default_authorizer = True

        # Find Authorizer
        authorizer_name = event_properties.get(SamApiProvider._AUTH, {}).get(SamApiProvider._AUTHORIZER, None)
        if authorizer_name == "NONE":
            # do not use any authorizers
            use_default_authorizer = False
            authorizer_name = None

        return (
            api_resource_id,
            Route(
                path=path,
                methods=[method],
                function_name=lambda_logical_id,
                event_type=event_type,
                payload_format_version=payload_format_version,
                stack_path=stack_path,
                authorizer_name=authorizer_name,
                use_default_authorizer=use_default_authorizer,
            ),
        )

    @staticmethod
    def merge_routes(collector: ApiCollector) -> List[Route]:
        """
        Quite often, an API is defined both in Implicit and Explicit Route definitions. In such cases, Implicit API
        definition wins because that conveys clear intent that the API is backed by a function. This method will
        merge two such list of routes with the right order of precedence. If a Path+Method combination is defined
        in both the places, only one wins.
        In a multi-stack situation, the API defined in the top level wins.

        Parameters
        ----------
        collector: samcli.lib.providers.api_collector.ApiCollector
            Collector object that holds all the APIs specified in the template

        Returns
        -------
        list of samcli.local.apigw.local_apigw_service.Route
            List of routes obtained by combining both the input lists.
        """

        implicit_routes = []
        explicit_routes = []

        # Store implicit and explicit APIs separately in order to merge them later in the correct order
        # Implicit APIs are defined on a resource with logicalID ServerlessRestApi
        for logical_id, apis in collector:
            if logical_id in (SamApiProvider.IMPLICIT_API_RESOURCE_ID, SamApiProvider.IMPLICIT_HTTP_API_RESOURCE_ID):
                implicit_routes.extend(apis)
            else:
                explicit_routes.extend(apis)

        # We will use "path+method" combination as key to this dictionary and store the Api config for this combination.
        # If an path+method combo already exists, then overwrite it if and only if this is an implicit API
        all_routes: Dict[str, Route] = {}

        # By adding implicit APIs to the end of the list, they will be iterated last. If a configuration was already
        # written by explicit API, it will be overridden by implicit API, just by virtue of order of iteration.
        # Within the explicit/implicit APIs, one defined in top level stack has the higher precedence. Here we
        # use depth of stack_path to sort APIs (desc).
        all_configs = sorted(explicit_routes, key=SamApiProvider._get_route_stack_depth, reverse=True) + sorted(
            implicit_routes, key=SamApiProvider._get_route_stack_depth, reverse=True
        )

        for config in all_configs:
            # Normalize the methods before de-duping to allow an ANY method in implicit API to override a regular HTTP
            # method on explicit route.
            for normalized_method in config.methods:
                key = config.path + normalized_method
                route = all_routes.get(key)
                if route and route.payload_format_version and config.payload_format_version is None:
                    config.payload_format_version = route.payload_format_version
                all_routes[key] = config

        result = set(all_routes.values())  # Assign to a set() to de-dupe
        LOG.debug(
            "Removed duplicates from '%d' Explicit APIs and '%d' Implicit APIs to produce '%d' APIs",
            len(explicit_routes),
            len(implicit_routes),
            len(result),
        )
        return list(result)

    @staticmethod
    def _get_route_stack_depth(route: Route) -> int:
        """
        Returns stack depth, used for sorted(routes, _get_route_stack_depth).
        Examples:
            "" (root stack), depth = 0
            "A" (1-level nested stack), depth = 1
            "A/B/C" (3-level nested stack), depth = 3
        """

        if not route.stack_path:
            return 0
        return route.stack_path.count("/") + 1

    @staticmethod
    def check_implicit_api_resource_ids(stacks: List[Stack]) -> None:
        for stack in stacks:
            for logical_id in stack.raw_resources:
                if logical_id in (
                    SamApiProvider.IMPLICIT_API_RESOURCE_ID,
                    SamApiProvider.IMPLICIT_HTTP_API_RESOURCE_ID,
                ):
                    LOG.warning(
                        Colored().yellow(
                            'Your template contains a resource with logical ID "%s", '
                            "which is a reserved logical ID in AWS SAM. "
                            "It could result in unexpected behaviors and is not recommended."
                        ),
                        logical_id,
                    )
