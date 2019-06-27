"""Class that parses the CloudFormation Api Template"""
import logging

from six import string_types

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.swagger.reader import SwaggerReader

LOG = logging.getLogger(__name__)


class CfnBaseApiProvider(object):
    RESOURCE_TYPE = "Type"

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
        for media_type in parser.get_binary_media_types() + binary_media:
            normalized_type = self.normalize_binary_media_type(media_type)
            if normalized_type:
                api.binary_media_types_set.add(normalized_type)
