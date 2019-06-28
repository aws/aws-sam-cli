"""Parses SAM given a template"""
import logging

from commands.local.lib.swagger.integration_uri import IntegrationType, LambdaUri
from local.apigw.local_apigw_service import Route
from samcli.commands.local.lib.cfn_base_api_provider import CfnBaseApiProvider

LOG = logging.getLogger(__name__)


class CfnApiProvider(CfnBaseApiProvider):
    APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
    APIGATEWAY_STAGE = "AWS::ApiGateway::Stage"
    APIGATEWAY_RESOURCE = "AWS::ApiGateway::Resource"
    APIGATEWAY_METHOD = "AWS::ApiGateway::Method"

    TYPES = [
        APIGATEWAY_RESTAPI,
        APIGATEWAY_STAGE,
        APIGATEWAY_RESOURCE,
        APIGATEWAY_METHOD
    ]

    def extract_resources(self, resources, collector, api, cwd=None):
        """
        Extract the Route Object from a given resource and adds it to the RouteCollector.

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template

        collector: samcli.commands.local.lib.route_collector.RouteCollector
            Instance of the API collector that where we will save the API information

        api: samcli.commands.local.lib.provider.Api
            Instance of the Api which will save all the api configurations

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        Return
        -------
        Returns a list of routes
        """
        for logical_id, resource in resources.items():
            resource_type = resource.get(CfnBaseApiProvider.RESOURCE_TYPE)
            if resource_type == CfnApiProvider.APIGATEWAY_RESTAPI:
                self._extract_cloud_formation_route(logical_id, resource, collector, api=api, cwd=cwd)

            if resource_type == CfnApiProvider.APIGATEWAY_STAGE:
                self._extract_cloud_formation_stage(resource, api)

            if resource_type == CfnApiProvider.APIGATEWAY_METHOD:
                self._extract_cloud_formation_method(logical_id, resource, collector, cwd=cwd)

        all_apis = []
        for _, apis in collector:
            all_apis.extend(apis)
        return all_apis

    def _extract_cloud_formation_route(self, logical_id, api_resource, collector, api, cwd=None):
        """
        Extract APIs from AWS::ApiGateway::RestApi resource by reading and parsing Swagger documents. The result is
        added to the collector.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        api_resource : dict
            Resource definition, including its properties

        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        """
        properties = api_resource.get("Properties", {})
        body = properties.get("Body")
        body_s3_location = properties.get("BodyS3Location")
        binary_media = properties.get("BinaryMediaTypes", [])

        if not body and not body_s3_location:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in Body and BodyS3Location",
                      logical_id)
            return
        self.extract_swagger_route(logical_id, body, body_s3_location, binary_media, collector, api, cwd)

    @staticmethod
    def _extract_cloud_formation_stage(api_resource, api):
        """
        Extract the stage from AWS::ApiGateway::Stage resource by reading and adds it to the collector.
        Parameters
       ----------
        api_resource : dict
            Resource definition, including its properties
        api: samcli.commands.local.lib.provider.Api
            Resource definition, including its properties
        """
        properties = api_resource.get("Properties", {})
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")
        logical_id = properties.get("RestApiId")
        if logical_id:
            api.stage_name = stage_name
            api.stage_variables = stage_variables

    def _extract_cloud_formation_method(self, api_resource, collector):
        """
        Extract APIs from AWS::ApiGateway::Method and work backwards up the tree to resolve and find the true path.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        api_resource : dict
            Resource definition, including its properties

        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        """

        properties = api_resource.get("Properties", {})
        parent_resource = properties.get("ResourceId")
        rest_api_id = properties.get("RestApiId")
        method = properties.get("HttpMethod")
        resource_path = self.resolve_resource_path(parent_resource, "")

        integration = properties.get("Integration")
        function_name = self._get_integration_function_name(integration)

        route = Route(method=method, function_name=function_name, path=resource_path)
        collector.add_routes(rest_api_id, [route])

    def resolve_resource_path(self, resource, current_path):
        properties = resource.get("Properties", {})
        parent_id = properties.get("ParentId")
        path_part = properties.get("PathPart")

        if parent_id:
            return self.resolve_resource_path(properties.get(parent_id), path_part + current_path)
        return current_path

    def _get_integration_function_name(self, integration):
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

        if integration \
                and isinstance(integration, dict) \
                and integration.get("type") == IntegrationType.aws_proxy.value:
            # Integration must be "aws_proxy" otherwise we don't care about it
            return LambdaUri.get_function_name(integration.get("uri"))
