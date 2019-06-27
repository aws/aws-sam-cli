"""Parses SAM given a template"""
import logging

from samcli.commands.local.lib.cf_base_api_provider import CFBaseApiProvider

LOG = logging.getLogger(__name__)


class CFApiProvider(CFBaseApiProvider):
    APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
    TYPES = [
        APIGATEWAY_RESTAPI
    ]

    def extract_resource_api(self, resources, collector, cwd=None):
        """
        Extract the Api Object from a given resource and adds it to the ApiCollector.

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template

        collector: ApiCollector
            Instance of the API collector that where we will save the API information

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        Return
        -------
        Returns a list of Apis
        """
        for logical_id, resource in resources.items():
            resource_type = resource.get(CFBaseApiProvider.RESOURCE_TYPE)
            if resource_type == CFApiProvider.APIGATEWAY_RESTAPI:
                self._extract_cloud_formation_api(logical_id, resource, collector, cwd)
        all_apis = []
        for _, apis in collector:
            all_apis.extend(apis)
        return all_apis

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
