"""Parses SAM given the template"""

import logging

from six import string_types

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.provider import ApiProvider, Api, Cors
from samcli.commands.local.lib.sam_base_provider import SamBaseProvider
from samcli.commands.local.lib.swagger.reader import SamSwaggerReader
from samcli.commands.local.lib.provider import Api, AbstractApiProvider

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.local.lib.cfn_base_api_provider import CfnBaseApiProvider

LOG = logging.getLogger(__name__)


class SamApiProvider(CfnBaseApiProvider):
    SERVERLESS_FUNCTION = "AWS::Serverless::Function"
    SERVERLESS_API = "AWS::Serverless::Api"
    TYPES = [
        SERVERLESS_FUNCTION,
        SERVERLESS_API
    ]
    _FUNCTION_EVENT_TYPE_API = "Api"
    _FUNCTION_EVENT = "Events"
    _EVENT_PATH = "Path"
    _EVENT_METHOD = "Method"
    _EVENT_TYPE = "Type"
    IMPLICIT_API_RESOURCE_ID = "ServerlessRestApi"

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
        # AWS::Serverless::Function is currently included when parsing of Apis because when SamBaseProvider is run on
        # the template we are creating the implicit apis due to plugins that translate it in the SAM repo,
        # which we later merge with the explicit ones in SamApiProvider.merge_apis. This requires the code to be
        # parsed here and in InvokeContext.
        for logical_id, resource in resources.items():
            resource_type = resource.get(CfnBaseApiProvider.RESOURCE_TYPE)
            if resource_type == SamApiProvider.SERVERLESS_FUNCTION:
                self._extract_apis_from_function(logical_id, resource, collector)
            if resource_type == SamApiProvider.SERVERLESS_API:
                self._extract_from_serverless_api(logical_id, resource, collector, cwd)
        return self.merge_apis(collector)

    def _extract_from_serverless_api(self, logical_id, api_resource, collector, cwd=None):
        """
        Extract APIs from AWS::Serverless::Api resource by reading and parsing Swagger documents. The result is added
        to the collector.

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
        body = properties.get("DefinitionBody")
        uri = properties.get("DefinitionUri")
        binary_media = properties.get("BinaryMediaTypes", [])
        cors = self._extract_cors(properties)
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")
        if not body and not uri:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in DefinitionBody and DefinitionUri",
                      logical_id)
            return
        self.extract_swagger_api(logical_id, body, uri, binary_media, collector, cwd)
        collector.add_stage_name(logical_id, stage_name)
        collector.add_stage_variables(logical_id, stage_variables)
        if cors:
            collector.add_cors(logical_id, cors)

    def _extract_cors(self, properties):
        """
        Extract Cors property from AWS::Serverless::Api resource by reading and parsing Swagger documents. The result
        is added to the Api.

        Parameters
        ----------
        properties : dict
            Resource properties
        """
        cors_prop = properties.get("Cors")
        cors = None
        if cors_prop and isinstance(cors_prop, dict):
            allow_methods = cors_prop.get("AllowMethods", ','.join(SamApiProvider._ANY_HTTP_METHODS))

            if allow_methods and "OPTIONS" not in allow_methods:
                allow_methods += ",OPTIONS"

            cors = Cors(
                allow_origin=cors_prop.get("AllowOrigin"),
                allow_methods=allow_methods,
                allow_headers=cors_prop.get("AllowHeaders"),
                max_age=cors_prop.get("MaxAge")
            )
        elif cors_prop and isinstance(cors_prop, string_types):
            cors = Cors(
                allow_origin=cors_prop,
                allow_methods=','.join(SamApiProvider._ANY_HTTP_METHODS),
                allow_headers=None,
                max_age=None
            )
        return cors

    def _extract_apis_from_function(self, logical_id, function_resource, collector):
        """
        Fetches a list of APIs configured for this SAM Function resource.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        function_resource : dict
            Contents of the function resource including its properties

        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        """

        resource_properties = function_resource.get("Properties", {})
        serverless_function_events = resource_properties.get(self._FUNCTION_EVENT, {})
        self.extract_apis_from_events(logical_id, serverless_function_events, collector)

    def extract_apis_from_events(self, function_logical_id, serverless_function_events, collector):
        """
        Given an AWS::Serverless::Function Event Dictionary, extract out all 'Api' events and store  within the
        collector

        Parameters
        ----------
        function_logical_id : str
            LogicalId of the AWS::Serverless::Function

        serverless_function_events : dict
            Event Dictionary of a AWS::Serverless::Function

        collector : ApiCollector
            Instance of the API collector that where we will save the API information
        """
        count = 0
        for _, event in serverless_function_events.items():

            if self._FUNCTION_EVENT_TYPE_API == event.get(self._EVENT_TYPE):
                api_resource_id, api = self._convert_event_api(function_logical_id, event.get("Properties"))
                collector.add_apis(api_resource_id, [api])
                count += 1

        LOG.debug("Found '%d' API Events in Serverless function with name '%s'", count, function_logical_id)

    @staticmethod
    def _convert_event_api(lambda_logical_id, event_properties):
        """
        Converts a AWS::Serverless::Function's Event Property to an Api configuration usable by the provider.

        :param str lambda_logical_id: Logical Id of the AWS::Serverless::Function
        :param dict event_properties: Dictionary of the Event's Property
        :return tuple: tuple of API resource name and Api namedTuple
        """
        path = event_properties.get(SamApiProvider._EVENT_PATH)
        method = event_properties.get(SamApiProvider._EVENT_METHOD)

        # An API Event, can have RestApiId property which designates the resource that owns this API. If omitted,
        # the API is owned by Implicit API resource. This could either be a direct resource logical ID or a
        # "Ref" of the logicalID
        api_resource_id = event_properties.get("RestApiId", SamApiProvider.IMPLICIT_API_RESOURCE_ID)
        if isinstance(api_resource_id, dict) and "Ref" in api_resource_id:
            api_resource_id = api_resource_id["Ref"]

        # This is still a dictionary. Something wrong with the template
        if isinstance(api_resource_id, dict):
            LOG.debug("Invalid RestApiId property of event %s", event_properties)
            raise InvalidSamDocumentException("RestApiId property of resource with logicalId '{}' is invalid. "
                                              "It should either be a LogicalId string or a Ref of a Logical Id string"
                                              .format(lambda_logical_id))

        return api_resource_id, Api(path=path, method=method, function_name=lambda_logical_id)

    @staticmethod
    def merge_apis(collector):
        """
        Quite often, an API is defined both in Implicit and Explicit API definitions. In such cases, Implicit API
        definition wins because that conveys clear intent that the API is backed by a function. This method will
        merge two such list of Apis with the right order of precedence. If a Path+Method combination is defined
        in both the places, only one wins.

        Parameters
        ----------
        collector : ApiCollector
            Collector object that holds all the APIs specified in the template

        Returns
        -------
        list of samcli.commands.local.lib.provider.Api
            List of APIs obtained by combining both the input lists.
        """

        implicit_apis = []
        explicit_apis = []

        # Store implicit and explicit APIs separately in order to merge them later in the correct order
        # Implicit APIs are defined on a resource with logicalID ServerlessRestApi
        for logical_id, apis in collector:
            if logical_id == SamApiProvider.IMPLICIT_API_RESOURCE_ID:
                implicit_apis.extend(apis)
            else:
                explicit_apis.extend(apis)

        # We will use "path+method" combination as key to this dictionary and store the Api config for this combination.
        # If an path+method combo already exists, then overwrite it if and only if this is an implicit API
        all_apis = {}

        # By adding implicit APIs to the end of the list, they will be iterated last. If a configuration was already
        # written by explicit API, it will be overriden by implicit API, just by virtue of order of iteration.
        all_configs = explicit_apis + implicit_apis

        for config in all_configs:
            # Normalize the methods before de-duping to allow an ANY method in implicit API to override a regular HTTP
            # method on explicit API.
            for normalized_method in AbstractApiProvider.normalize_http_methods(config.method):
                key = config.path + normalized_method
                all_apis[key] = config

        result = set(all_apis.values())  # Assign to a set() to de-dupe
        LOG.debug("Removed duplicates from '%d' Explicit APIs and '%d' Implicit APIs to produce '%d' APIs",
                  len(explicit_apis), len(implicit_apis), len(result))

        return list(result)
