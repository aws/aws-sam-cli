"""Parses SAM given a template"""
import logging
from typing import Any, Dict, Optional, Tuple, List, cast

from samcli.commands.local.lib.swagger.integration_uri import LambdaUri
from samcli.lib.providers.provider import Stack
from samcli.local.apigw.local_apigw_service import Route
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.lib.providers.cfn_base_api_provider import CfnBaseApiProvider
from samcli.lib.providers.api_collector import ApiCollector

from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_METHOD,
    AWS_APIGATEWAY_RESOURCE,
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_STAGE,
    AWS_APIGATEWAY_V2_API,
    AWS_APIGATEWAY_V2_INTEGRATION,
    AWS_APIGATEWAY_V2_ROUTE,
    AWS_APIGATEWAY_V2_STAGE,
)

LOG = logging.getLogger(__name__)


class CfnApiProvider(CfnBaseApiProvider):
    METHOD_BINARY_TYPE = "CONVERT_TO_BINARY"
    HTTP_API_PROTOCOL_TYPE = "HTTP"
    TYPES = [
        AWS_APIGATEWAY_RESTAPI,
        AWS_APIGATEWAY_STAGE,
        AWS_APIGATEWAY_RESOURCE,
        AWS_APIGATEWAY_METHOD,
        AWS_APIGATEWAY_V2_API,
        AWS_APIGATEWAY_V2_INTEGRATION,
        AWS_APIGATEWAY_V2_ROUTE,
        AWS_APIGATEWAY_V2_STAGE,
    ]

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

        for stack in stacks:
            resources = stack.resources
            for logical_id, resource in resources.items():
                resource_type = resource.get(CfnBaseApiProvider.RESOURCE_TYPE)
                if resource_type == AWS_APIGATEWAY_RESTAPI:
                    self._extract_cloud_formation_route(stack.stack_path, logical_id, resource, collector, cwd=cwd)

                if resource_type == AWS_APIGATEWAY_STAGE:
                    self._extract_cloud_formation_stage(resources, resource, collector)

                if resource_type == AWS_APIGATEWAY_METHOD:
                    self._extract_cloud_formation_method(stack.stack_path, resources, logical_id, resource, collector)

                if resource_type == AWS_APIGATEWAY_V2_API:
                    self._extract_cfn_gateway_v2_api(stack.stack_path, logical_id, resource, collector, cwd=cwd)

                if resource_type == AWS_APIGATEWAY_V2_ROUTE:
                    self._extract_cfn_gateway_v2_route(stack.stack_path, resources, logical_id, resource, collector)

                if resource_type == AWS_APIGATEWAY_V2_STAGE:
                    self._extract_cfn_gateway_v2_stage(resources, resource, collector)

    @staticmethod
    def _extract_cloud_formation_route(
        stack_path: str,
        logical_id: str,
        api_resource: Dict[str, Any],
        collector: ApiCollector,
        cwd: Optional[str] = None,
    ) -> None:
        """
        Extract APIs from AWS::ApiGateway::RestApi resource by reading and parsing Swagger documents. The result is
        added to the collector.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        logical_id : str
            Logical ID of the resource
        api_resource : dict
            Resource definition, including its properties
        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        cwd : Optional[str]
            An optional string to override the current working directory
        """
        properties = api_resource.get("Properties", {})
        body = properties.get("Body")
        body_s3_location = properties.get("BodyS3Location")
        binary_media = properties.get("BinaryMediaTypes", [])

        if not body and not body_s3_location:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in Body and BodyS3Location", logical_id)
            return
        CfnBaseApiProvider.extract_swagger_route(
            stack_path, logical_id, body, body_s3_location, binary_media, collector, cwd
        )

    @staticmethod
    def _extract_cloud_formation_stage(
        resources: Dict[str, Dict], stage_resource: Dict, collector: ApiCollector
    ) -> None:
        """
         Extract the stage from AWS::ApiGateway::Stage resource by reading and adds it to the collector.
         Parameters
        ----------
         resources: dict
             All Resource definition, including its properties

         stage_resource : dict
             Stage Resource definition, including its properties

         collector : ApiCollector
             Instance of the API collector that where we will save the API information
        """
        properties = stage_resource.get("Properties", {})
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")

        logical_id = properties.get("RestApiId")
        if not logical_id:
            raise InvalidSamTemplateException("The AWS::ApiGateway::Stage must have a RestApiId property")
        rest_api_resource_type = resources.get(logical_id, {}).get("Type")
        if rest_api_resource_type != AWS_APIGATEWAY_RESTAPI:
            raise InvalidSamTemplateException(
                "The AWS::ApiGateway::Stage must have a valid RestApiId that points to RestApi resource {}".format(
                    logical_id
                )
            )

        collector.stage_name = stage_name
        collector.stage_variables = stage_variables

    def _extract_cloud_formation_method(
        self,
        stack_path: str,
        resources: Dict[str, Dict],
        logical_id: str,
        method_resource: Dict,
        collector: ApiCollector,
    ) -> None:
        """
        Extract APIs from AWS::ApiGateway::Method and work backwards up the tree to resolve and find the true path.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        resources: dict
            All Resource definition, including its properties

        logical_id : str
            Logical ID of the resource

        method_resource : dict
            Resource definition, including its properties

        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        """

        properties = method_resource.get("Properties", {})
        resource_id = properties.get("ResourceId")
        rest_api_id = properties.get("RestApiId")
        method = properties.get("HttpMethod")
        operation_name = properties.get("OperationName")

        resource_path = "/"
        if isinstance(resource_id, str):  # If the resource_id resolves to a string
            resource = resources.get(resource_id)

            if resource:
                resource_path = self.resolve_resource_path(resources, resource, "")
            else:
                # This is the case that a raw ref resolves to a string { "Fn::GetAtt": ["MyRestApi", "RootResourceId"] }
                resource_path = resource_id

        integration = properties.get("Integration", {})
        content_type = integration.get("ContentType")

        # CORS can be set through AWS::ApiGateway::Method IntegrationResponses.ResponseParameters
        # This is how CDK sets defaultCorsPreflightOptions
        cors = None
        integration_responses = integration.get("IntegrationResponses")
        if integration_responses:
            for responses in integration_responses:
                response_parameters = responses.get("ResponseParameters")
                if response_parameters:
                    cors = self.extract_cors_from_method(response_parameters)
        if cors:
            collector.cors = cors

        content_handling = integration.get("ContentHandling")

        if content_handling == CfnApiProvider.METHOD_BINARY_TYPE and content_type:
            collector.add_binary_media_types(logical_id, [content_type])

        routes = Route(
            methods=[method],
            function_name=self._get_integration_function_name(integration),
            path=resource_path,
            operation_name=operation_name,
            stack_path=stack_path,
        )
        collector.add_routes(rest_api_id, [routes])

    def _extract_cfn_gateway_v2_api(
        self,
        stack_path: str,
        logical_id: str,
        api_resource: Dict,
        collector: ApiCollector,
        cwd: Optional[str] = None,
    ) -> None:
        """
        Extract APIs from AWS::ApiGatewayV2::Api resource by reading and parsing Swagger documents. The result is
        added to the collector. If the Swagger documents is not available, it can add a catch-all route based on
        the target function.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        logical_id : str
            Logical ID of the resource
        api_resource : dict
            Resource definition, including its properties
        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        cwd : Optional[str]
            An optional string to override the current working directory
        """
        properties = api_resource.get("Properties", {})
        body = properties.get("Body")
        body_s3_location = properties.get("BodyS3Location")
        cors = self.extract_cors_http(properties.get("CorsConfiguration"))
        target = properties.get("Target")
        route_key = properties.get("RouteKey")
        protocol_type = properties.get("ProtocolType")

        if not body and not body_s3_location:
            LOG.debug("Swagger document not found in Body and BodyS3Location for resource '%s'.", logical_id)
            if cors:
                collector.cors = cors
            if target and protocol_type == CfnApiProvider.HTTP_API_PROTOCOL_TYPE:
                method, path = self._parse_route_key(route_key)
                routes = Route(
                    methods=[method],
                    path=path,
                    function_name=LambdaUri.get_function_name(target),
                    event_type=Route.HTTP,
                    stack_path=stack_path,
                )
                collector.add_routes(logical_id, [routes])
            return

        CfnBaseApiProvider.extract_swagger_route(
            stack_path, logical_id, body, body_s3_location, None, collector, cwd, Route.HTTP
        )

    def _extract_cfn_gateway_v2_route(
        self,
        stack_path: str,
        resources: Dict[str, Dict],
        logical_id: str,
        route_resource: Dict,
        collector: ApiCollector,
    ) -> None:
        """
        Extract APIs from AWS::ApiGatewayV2::Route, and link it with the integration resource to get the lambda
        function.

        Parameters
        ----------
        stack_path : str
            Path of the stack the resource is located

        resources: dict
            All Resource definition, including its properties

        logical_id : str
            Logical ID of the resource

        route_resource : dict
            Resource definition, including its properties

        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        """

        properties = route_resource.get("Properties", {})
        api_id = properties.get("ApiId")
        route_key = properties.get("RouteKey")
        integration_target = properties.get("Target")
        operation_name = properties.get("OperationName")

        if integration_target:
            function_name, payload_format_version = self._get_route_function_name(resources, integration_target)
        else:
            LOG.debug(
                "Skipping The AWS::ApiGatewayV2::Route '%s', as it does not contain an integration for a Lambda "
                "Function",
                logical_id,
            )
            return

        method, path = self._parse_route_key(route_key)

        if not route_key or not method or not path:
            LOG.debug("The AWS::ApiGatewayV2::Route '%s' does not have a correct route key '%s'", logical_id, route_key)
            raise InvalidSamTemplateException(
                "The AWS::ApiGatewayV2::Route {} does not have a correct route key {}".format(logical_id, route_key)
            )

        routes = Route(
            methods=[method],
            path=path,
            function_name=function_name,
            event_type=Route.HTTP,
            payload_format_version=payload_format_version,
            operation_name=operation_name,
            stack_path=stack_path,
        )
        collector.add_routes(api_id, [routes])

    def resolve_resource_path(
        self,
        resources: Dict[str, Dict],
        resource: Dict,
        current_path: str,
    ) -> str:
        """
        Extract path from the Resource object by going up the tree

        Parameters
        ----------
        resources: dict
            Dictionary containing all the resources to resolve

        resource : dict
            AWS::ApiGateway::Resource definition and its properties

        current_path : str
            Current path resolved so far
        """

        properties = resource.get("Properties", {})
        parent_id = cast(str, properties.get("ParentId"))
        resource_path = cast(str, properties.get("PathPart"))
        parent = resources.get(parent_id)
        if parent:
            return self.resolve_resource_path(resources, parent, "/" + resource_path + current_path)
        if parent_id:
            return parent_id + resource_path + current_path

        return "/" + resource_path + current_path

    @staticmethod
    def _extract_cfn_gateway_v2_stage(
        resources: Dict[str, Dict],
        stage_resource: Dict,
        collector: ApiCollector,
    ) -> None:
        """
         Extract the stage from AWS::ApiGatewayV2::Stage resource by reading and adds it to the collector.
         Parameters
        ----------
         resources: dict
             All Resource definition, including its properties

         stage_resource : dict
             Stage Resource definition, including its properties

         collector : ApiCollector
             Instance of the API collector that where we will save the API information
        """
        properties = stage_resource.get("Properties", {})
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")

        api_id = properties.get("ApiId")
        if not api_id:
            raise InvalidSamTemplateException("The AWS::ApiGatewayV2::Stage must have a ApiId property")
        api_resource_type = resources.get(api_id, {}).get("Type")
        if api_resource_type != AWS_APIGATEWAY_V2_API:
            raise InvalidSamTemplateException(
                "The AWS::ApiGatewayV2::Stag must have a valid ApiId that points to Api resource {}".format(api_id)
            )

        collector.stage_name = stage_name
        collector.stage_variables = stage_variables

    @staticmethod
    def _get_integration_function_name(integration: Dict) -> Optional[str]:
        """
        Tries to parse the Lambda Function name from the Integration defined in the method configuration. Integration
        configuration. We care only about Lambda integrations, which are of type aws_proxy, and ignore the rest.
        Integration URI is complex and hard to parse. Hence we do our best to extract function name out of
        integration URI. If not possible, we return None.

        Parameters
        ----------
        integration : Dict
            the integration defined in the method configuration

        Returns
        -------
        string or None
            Lambda function name, if possible. None, if not.
        """

        if integration and isinstance(integration, dict):
            # Integration must be "aws_proxy" otherwise we don't care about it
            uri: str = cast(str, integration.get("Uri"))
            return LambdaUri.get_function_name(uri)

        return None

    @staticmethod
    def _get_route_function_name(
        resources: Dict[str, Dict], integration_target: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Look for the APIGateway integration resource based on the input integration_target, then try to parse the
        lambda function from the the integration resource properties.
        It also gets the Payload format version from the API Gateway integration resource.

        Parameters
        ----------
        resources : dict
            dictionary of all resources.

        integration_target : str
            the path of the HTTP Gateway integration resource

        Returns
        -------
        string or None, string or None
            Lambda function name, if possible. None, if not.
            Payload format version, if possible. None, if not
        """

        integration_id = integration_target.split("/")[1].strip()
        integration_resource = resources.get(integration_id, {})
        resource_type = integration_resource.get("Type")

        if resource_type == AWS_APIGATEWAY_V2_INTEGRATION:
            properties = integration_resource.get("Properties", {})
            integration_uri = properties.get("IntegrationUri")
            payload_format_version = properties.get("PayloadFormatVersion")
            if integration_uri and isinstance(integration_uri, str):
                return LambdaUri.get_function_name(integration_uri), payload_format_version

        return None, None

    @staticmethod
    def _parse_route_key(route_key: Optional[str]) -> Tuple[str, str]:
        """
        parse the route key, and return the methods && path.
        route key should be in format "Http_method Path" or to equal "$default"
        if the route key is $default, return 'X-AMAZON-APIGATEWAY-ANY-METHOD' as a method && $default as a path
        else we will split the route key on space and use the specified method and path

        Parameters
        ----------
        route_key : str
            the defined route key.

        Returns
        -------
        string, string
            method as defined in the route key or X-AMAZON-APIGATEWAY-ANY-METHOD .
            route key path if defined or $default.
        """
        if not route_key or route_key == "$default":
            return "X-AMAZON-APIGATEWAY-ANY-METHOD", "$default"

        # whitespace is the default split character as per this documentation
        # https://docs.python.org/3/library/stdtypes.html#str.split
        [method, path] = route_key.split()
        return method, path
