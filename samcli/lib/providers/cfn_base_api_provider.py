"""Class that parses the CloudFormation Api Template"""
import logging

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.swagger.reader import SwaggerReader

LOG = logging.getLogger(__name__)


class CfnBaseApiProvider:
    RESOURCE_TYPE = "Type"

    def extract_resources(self, resources, collector, cwd=None):
        """Extract the Route Object from a given resource and adds it to the RouteCollector.

        Parameters
        ----------
        resources :

        collector :

        cwd :
             (Default value = None)

        Returns
        -------


        """
        raise NotImplementedError("not implemented")

    def extract_swagger_route(self, logical_id, body, uri, binary_media, collector, cwd=None):
        """Parse the Swagger documents and adds it to the ApiCollector.

        Parameters
        ----------
        logical_id :

        body :

        uri :

        binary_media :

        collector :

        cwd :
             (Default value = None)

        Returns
        -------


        """
        reader = SwaggerReader(definition_body=body, definition_uri=uri, working_dir=cwd)
        swagger = reader.read()
        parser = SwaggerParser(swagger)
        routes = parser.get_routes()
        LOG.debug("Found '%s' APIs in resource '%s'", len(routes), logical_id)

        collector.add_routes(logical_id, routes)

        collector.add_binary_media_types(logical_id, parser.get_binary_media_types())  # Binary media from swagger
        collector.add_binary_media_types(logical_id, binary_media)  # Binary media specified on resource in template
