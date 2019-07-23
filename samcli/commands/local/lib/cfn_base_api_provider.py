"""Class that parses the CloudFormation Api Template"""

import logging

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.swagger.reader import SamSwaggerReader

LOG = logging.getLogger(__name__)


class CfnBaseApiProvider(object):
    RESOURCE_TYPE = "Type"

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
        raise NotImplementedError("not implemented")

    @staticmethod
    def extract_swagger_api(logical_id, body, uri, binary_media, collector, cwd=None):
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

        collector: ApiCollector
            Instance of the API collector that where we will save the API information

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file
        """
        reader = SamSwaggerReader(definition_body=body,
                                  definition_uri=uri,
                                  working_dir=cwd)
        swagger = reader.read()
        parser = SwaggerParser(swagger)
        apis = parser.get_apis()
        LOG.debug("Found '%s' APIs in resource '%s'", len(apis), logical_id)

        collector.add_apis(logical_id, apis)
        collector.add_binary_media_types(logical_id, parser.get_binary_media_types())  # Binary media from swagger
        collector.add_binary_media_types(logical_id, binary_media)  # Binary media specified on resource in template
