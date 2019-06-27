"""Parses SAM given a template"""
import logging

from samcli.commands.local.lib.cf_base_api_provider import CFBaseApiProvider

LOG = logging.getLogger(__name__)


class CFApiProvider(CFBaseApiProvider):
    APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
    TYPES = [
        APIGATEWAY_RESTAPI
    ]

    def extract_resource_api(self, resource_type, logical_id, api_resource, collector, cwd=None):
        if resource_type == CFApiProvider.APIGATEWAY_RESTAPI:
            return self._extract_cloud_formation_api(logical_id, api_resource, collector, cwd)

    def _extract_cloud_formation_api(self, logical_id, api_resource, collector, cwd=None):
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
        s3_location = properties.get("BodyS3Location")
        binary_media = properties.get("BinaryMediaTypes", [])

        if not body and not s3_location:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in Body and BodyS3Location",
                      logical_id)
            return
        self.extract_swagger_api(logical_id, body, s3_location, binary_media, collector, cwd)
