"""Parses SAM given a template"""
import logging

from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.commands.local.lib.cfn_base_api_provider import CfnBaseApiProvider

LOG = logging.getLogger(__name__)


class CfnApiProvider(CfnBaseApiProvider):
    APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
    APIGATEWAY_STAGE = "AWS::ApiGateway::Stage"
    TYPES = [
        APIGATEWAY_RESTAPI,
        APIGATEWAY_STAGE
    ]

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
            LOG.debug("Skipping resource '%s'. Swagger document not found in Body and BodyS3Location",
                      logical_id)
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

        # Currently, we aren't resolving any Refs or other intrinsic properties that come with it
        # A separate pr will need to fully resolve intrinsics
        logical_id = properties.get("RestApiId")
        if not logical_id:
            raise InvalidSamTemplateException("The AWS::ApiGateway::Stage must have a RestApiId property")

        rest_api_resource_type = resources.get(logical_id, {}).get("Type")
        if rest_api_resource_type != CfnApiProvider.APIGATEWAY_RESTAPI:
            raise InvalidSamTemplateException(
                "The AWS::ApiGateway::Stage must have a valid RestApiId that points to RestApi resource {}".format(
                    logical_id))

        collector.stage_name = stage_name
        collector.stage_variables = stage_variables
