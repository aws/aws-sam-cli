"""Class that parses the CloudFormation Api Template"""
import logging

from six import string_types

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.swagger.reader import SwaggerReader

LOG = logging.getLogger(__name__)


class CfnBaseApiProvider(object):
    RESOURCE_TYPE = "Type"
    ANY_HTTP_METHODS = ["GET",
                        "DELETE",
                        "PUT",
                        "POST",
                        "HEAD",
                        "OPTIONS",
                        "PATCH"]

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
        raise NotImplementedError("not implemented")

    @staticmethod
    def normalize_binary_media_type(value):
        """
        Converts binary media types values to the canonical format. Ex: image~1gif -> image/gif. If the value is not
        a string, then this method just returns None
        Parameters
        ----------
        value : str
            Value to be normalized
        Returns
        -------
        str or None
            Normalized value. If the input was not a string, then None is returned
        """

        if not isinstance(value, string_types):
            # It is possible that user specified a dict value for one of the binary media types. We just skip them
            return None

        return value.replace("~1", "/")

    def extract_swagger_route(self, logical_id, body, uri, binary_media, collector, api, cwd=None):
        """
        Parse the Swagger documents and adds it to the ApiCollector.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        body : dict
            The body of the RestApi

        uri : str or dict
            The url to location of the RestApi

        binary_media: list
            The link to the binary media

        collector: samcli.commands.local.lib.route_collector.RouteCollector
            Instance of the Route collector that where we will save the route information

        api: samcli.commands.local.lib.provider.Api
            Instance of the Api which will save all the api configurations

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file
        """
        reader = SwaggerReader(definition_body=body,
                               definition_uri=uri,
                               working_dir=cwd)
        swagger = reader.read()
        parser = SwaggerParser(swagger)
        routes = parser.get_routes()
        LOG.debug("Found '%s' APIs in resource '%s'", len(routes), logical_id)

        collector.add_routes(logical_id, routes)

        self.add_binary_media_types(logical_id, api, parser.get_binary_media_types())  # Binary media from swagger
        self.add_binary_media_types(logical_id, api, binary_media)  # Binary media specified on resource in template

    def add_binary_media_types(self, logical_id, api, binary_media_types):
        """
        Stores the binary media type configuration for the API with given logical ID
        Parameters
        ----------

        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        api: samcli.commands.local.lib.provider.Api
            Instance of the Api which will save all the api configurations

        binary_media_types : list of str
            List of binary media types supported by this resource
        """

        binary_media_types = binary_media_types or []
        for value in binary_media_types:
            normalized_value = self.normalize_binary_media_type(value)

            # If the value is not supported, then just skip it.
            if normalized_value:
                api.binary_media_types_set.add(normalized_value)
            else:
                LOG.debug("Unsupported data type of binary media type value of resource '%s'", logical_id)
