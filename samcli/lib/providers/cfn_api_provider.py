"""Parses SAM given a template"""
import logging

from six import string_types

from samcli.commands.local.lib.swagger.integration_uri import LambdaUri
from samcli.local.apigw.local_apigw_service import Route
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.lib.providers.cfn_base_api_provider import CfnBaseApiProvider

LOG = logging.getLogger(__name__)


class CfnApiProvider(CfnBaseApiProvider):
    APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
    APIGATEWAY_STAGE = "AWS::ApiGateway::Stage"
    APIGATEWAY_RESOURCE = "AWS::ApiGateway::Resource"
    APIGATEWAY_METHOD = "AWS::ApiGateway::Method"
    METHOD_BINARY_TYPE = "CONVERT_TO_BINARY"
    TYPES = [APIGATEWAY_RESTAPI, APIGATEWAY_STAGE, APIGATEWAY_RESOURCE, APIGATEWAY_METHOD]

    def extract_resources(self, resources, collector, cwd=None):
        """
        Extract the Route Object from a given resource and adds it to the RouteCollector.

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template

        collector: samcli.commands.local.lib.route_collector.RouteCollector
            Instance of the API collector that where we will save the API information

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        Return
        -------
        Returns a list of routes
        """

        for logical_id, resource in resources.items():
            resource_type = resource.get(CfnBaseApiProvider.RESOURCE_TYPE)
            if resource_type == CfnApiProvider.APIGATEWAY_RESTAPI:
                self._extract_cloud_formation_route(logical_id, resource, collector, cwd=cwd)

            if resource_type == CfnApiProvider.APIGATEWAY_STAGE:
                self._extract_cloud_formation_stage(resources, resource, collector)

            if resource_type == CfnApiProvider.APIGATEWAY_METHOD:
                self._extract_cloud_formation_method(resources, logical_id, resource, collector)

        all_apis = []
        for _, apis in collector:
            all_apis.extend(apis)
        return all_apis

    def _extract_cloud_formation_route(self, logical_id, api_resource, collector, cwd=None):
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
            LOG.debug("Skipping resource '%s'. Swagger document not found in Body and BodyS3Location", logical_id)
            return
        self.extract_swagger_route(logical_id, body, body_s3_location, binary_media, collector, cwd)

    @staticmethod
    def _extract_cloud_formation_stage(resources, stage_resource, collector):
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
        if rest_api_resource_type != CfnApiProvider.APIGATEWAY_RESTAPI:
            raise InvalidSamTemplateException(
                "The AWS::ApiGateway::Stage must have a valid RestApiId that points to RestApi resource {}".format(
                    logical_id
                )
            )

        collector.stage_name = stage_name
        collector.stage_variables = stage_variables

    def _extract_cloud_formation_method(self, resources, logical_id, method_resource, collector):
        """
        Extract APIs from AWS::ApiGateway::Method and work backwards up the tree to resolve and find the true path.

        Parameters
        ----------
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

        resource_path = "/"
        if isinstance(resource_id, string_types):  # If the resource_id resolves to a string
            resource = resources.get(resource_id)

            if resource:
                resource_path = self.resolve_resource_path(resources, resource, "")
            else:
                # This is the case that a raw ref resolves to a string { "Fn::GetAtt": ["MyRestApi", "RootResourceId"] }
                resource_path = resource_id

        integration = properties.get("Integration", {})
        content_type = integration.get("ContentType")

        content_handling = integration.get("ContentHandling")

        if content_handling == CfnApiProvider.METHOD_BINARY_TYPE and content_type:
            collector.add_binary_media_types(logical_id, [content_type])

        routes = Route(
            methods=[method], function_name=self._get_integration_function_name(integration), path=resource_path
        )
        collector.add_routes(rest_api_id, [routes])

    def resolve_resource_path(self, resources, resource, current_path):
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
        parent_id = properties.get("ParentId")
        resource_path = properties.get("PathPart")
        parent = resources.get(parent_id)
        if parent:
            return self.resolve_resource_path(resources, parent, "/" + resource_path + current_path)
        if parent_id:
            return parent_id + resource_path + current_path

        return "/" + resource_path + current_path

    @staticmethod
    def _get_integration_function_name(integration):
        """
        Tries to parse the Lambda Function name from the Integration defined in the method configuration. Integration
        configuration. We care only about Lambda integrations, which are of type aws_proxy, and ignore the rest.
        Integration URI is complex and hard to parse. Hence we do our best to extract function name out of
        integration URI. If not possible, we return None.

        Parameters
        ----------
        method_config : dict
            Dictionary containing the method configuration which might contain integration settings

        Returns
        -------
        string or None
            Lambda function name, if possible. None, if not.
        """

        if integration and isinstance(integration, dict):
            # Integration must be "aws_proxy" otherwise we don't care about it
            return LambdaUri.get_function_name(integration.get("Uri"))

        return None
