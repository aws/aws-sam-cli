"""Class that provides the Api with a list of routes from a Template"""

import logging
from collections import defaultdict

from six import string_types

from samcli.commands.local.lib.provider import AbstractApiProvider, Api
from samcli.commands.local.lib.sam_base_provider import SamBaseProvider
from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.swagger.reader import SwaggerReader
from samcli.local.apigw.local_apigw_service import Route

LOG = logging.getLogger(__name__)


class ApiProvider(AbstractApiProvider):
    IMPLICIT_API_RESOURCE_ID = "ServerlessRestApi"
    _TYPE = "Type"

    PROVIDER_TYPE_CLOUD_FORMATION = "CF"

    def __init__(self, template_dict, parameter_overrides=None, cwd=None,
                 provider_type=None):
        """
        Initialize the class with template data. The template_dict is assumed
        to be valid, normalized and a dictionary. template_dict should be normalized by running any and all
        pre-processing before passing to this class.
        This class does not perform any syntactic validation of the template.

        After the class is initialized, changes to ``template_dict`` will not be reflected in here.
        You will need to explicitly update the class with new template, if necessary.

        Parameters
        ----------
        template_dict : dict
            Template as a dictionary

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        provider_type: AbstractParserProvider
            Object to parse the api configurations
        """
        self.provider_type = provider_type or self.PROVIDER_TYPE_CLOUD_FORMATION

        if self.provider_type != self.PROVIDER_TYPE_CLOUD_FORMATION:
            raise NotImplementedError("not implemented")

        self.template_dict = SamBaseProvider.get_template(template_dict, parameter_overrides)
        self.resources = self.template_dict.get("Resources", {})

        LOG.debug("%d resources found in the template", len(self.resources))

        # Store a set of apis
        self.cwd = cwd
        self.api = Api()
        self.routes = self._extract_routes(self.resources)

        LOG.debug("%d APIs found in the template", len(self.routes))

    def get_all(self):
        """
        Yields all the Lambda functions with Api Events available in the Template.

        :yields Api: namedtuple containing the Api information
        """

        for api in self.routes:
            yield api

    def _extract_routes(self, resources):
        """
        Extract all Routes from the resource

        :param dict resources: Dictionary of resources
        :return: List of nametuple Api
        """

        collector = RouteCollector()
        providers = {Provider.RESOURCE_TYPE: Provider() for Provider in AbstractParserProvider.__subclasses__() if
                     Provider.PROVIDER_TYPE == self.provider_type}

        for logical_id, resource in resources.items():
            resource_type = resource.get(ApiProvider._TYPE)
            provider = providers.get(resource_type)
            if provider:
                provider.extract_route(logical_id, resource, collector, api=self.api, cwd=self.cwd)

        routes = ApiProvider._merge_routes(collector)
        return routes

    @staticmethod
    def _merge_routes(collector):
        """
        Quite often, an API is defined both in Implicit and Explicit Route definitions. In such cases, Implicit Route
        definition wins because that conveys clear intent that the Route is backed by a function. This method will
        merge two such list of Routes with the right order of precedence. If a Path+Method combination is defined
        in both the places, only one wins.

        Parameters
        ----------
        collector : RouteCollector
            Collector object that holds all the APIs specified in the template

        Returns
        -------
        list of samcli.commands.local.lib.provider.Api
            List of APIs obtained by combining both the input lists.
        """

        implicit_routes = []
        explicit_routes = []

        # Store implicit and explicit routes separately in order to merge them later in the correct order
        # Implicit routes are defined on a resource with logicalID ServerlessRestApi
        for logical_id, routes in collector:
            if logical_id == ApiProvider.IMPLICIT_API_RESOURCE_ID:
                implicit_routes.extend(routes)
            else:
                explicit_routes.extend(routes)

        # We will use "path+method" combination as key to this dictionary and store the Api config for this combination.
        # If an path+method combo already exists, then overwrite it if and only if this is an implicit API
        all_routes = {}

        # By adding implicit routes to the end of the list, they will be iterated last. If a configuration was already
        # written by explicit routes, it will be overriden by implicit route, just by virtue of order of iteration.
        all_configs = explicit_routes + implicit_routes

        for config in all_configs:
            key = config.path + config.method
            all_routes[key] = config

        result = set(all_routes.values())  # Assign to a set() to de-dupe
        LOG.debug("Removed duplicates from '%d' Explicit APIs and '%d' Implicit APIs to produce '%d' APIs",
                  len(explicit_routes), len(implicit_routes), len(result))

        return list(result)

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


class RouteCollector(object):
    """
    Class to store the API configurations in the Template. This class helps store both implicit and explicit
    APIs in a standardized format
    """

    def __init__(self):
        # API properties stored per resource.
        self.by_resource = defaultdict(list)

    def __iter__(self):
        """
        Iterator to iterate through all the APIs stored in the collector. In each iteration, this yields the
        LogicalId of the API resource and a list of APIs available in this resource.
        Yields
        -------
        str
            LogicalID of the AWS::Serverless::Api resource
        list samcli.commands.local.lib.provider.Api
            List of the API available in this resource along with additional configuration like binary media types.
        """

        for logical_id, _ in self.by_resource.items():
            yield logical_id, self._get_routes(logical_id)

    def add_routes(self, logical_id, apis):
        """
        Stores the given APIs tagged under the given logicalId
        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api resource
        apis : list of samcli.commands.local.agiw.local_apigw_service.Route
            List of APIs available in this resource
        """
        self._get_routes(logical_id).extend(apis)

    def _get_routes(self, logical_id):
        """
        Returns the properties of resource with given logical ID. If a resource is not found, then it returns an
        empty data.
        Parameters
        ----------
        logical_id : str
            Logical ID of the resource
        Returns
        -------
        samcli.commands.local.lib.Routes
            Properties object for this resource.
        """

        return self.by_resource[logical_id]


class AbstractParserProvider(object):
    """
    Abstract Class to parse the api configurations. This makes it an easier transition to supporting multiple formats.
    """

    def extract_route(self, logical_id, api_resource, collector, api, cwd=None):
        """
        Extract the Api Object from a given resource and adds it to the ApiCollector.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        api_resource : dict
            Resource definition, including its properties

        collector: RouteCollector
            Instance of the Route collector that where we will save the Route information

        api: Api
            Instance of the Api object to collect all the attributes associated with it.

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        """
        raise NotImplementedError("not implemented")

    @staticmethod
    def extract_swagger_routes(logical_id, body, uri, binary_media, collector, api, cwd=None):
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

        collector: RouteCollector
            Instance of the API collector that where we will save the API information

        api: Api
            Instance of the Api object to collect all the attributes associated with it.

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
            normalized_type = ApiProvider.normalize_binary_media_type(media_type)
            if normalized_type:
                api.binary_media_types_set.add(normalized_type)


class FunctionParserProvider(AbstractParserProvider):
    RESOURCE_TYPE = "AWS::Serverless::Function"
    PROVIDER_TYPE = ApiProvider.PROVIDER_TYPE_CLOUD_FORMATION
    _FUNCTION_EVENT_TYPE_ROUTE = "Api"
    _FUNCTION_EVENT = "Events"
    _EVENT_PATH = "Path"
    _EVENT_METHOD = "Method"
    _EVENT_TYPE = "Type"

    def extract_route(self, logical_id, api_resource, collector, api, cwd=None):
        """
        Extract the Api Object from a given resource and adds it to the ApiCollector.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        api_resource: dict
            Contents of the function resource including its properties\

        collector: RouteCollector
            Instance of the API collector that where we will save the API information

        api: Api
            Instance of the Api object to collect all the attributes associated with it.

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        """
        return self._extract_routes_from_function(logical_id, api_resource, collector)

    def _extract_routes_from_function(self, logical_id, function_resource, collector):
        """
        Fetches a list of APIs configured for this SAM Function resource.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        function_resource : dict
            Contents of the function resource including its properties

        collector : RouteCollector
            Instance of the API collector that where we will save the API information
        """

        resource_properties = function_resource.get("Properties", {})
        serverless_function_events = resource_properties.get(self._FUNCTION_EVENT, {})
        self.extract_routes_from_events(logical_id, serverless_function_events, collector)

    def extract_routes_from_events(self, function_logical_id, serverless_function_events, collector):
        """
        Given an AWS::Serverless::Function Event Dictionary, extract out all 'Api' events and store  within the
        collector

        Parameters
        ----------
        function_logical_id : str
            LogicalId of the AWS::Serverless::Function

        serverless_function_events : dict
            Event Dictionary of a AWS::Serverless::Function

        collector : RouteCollector
            Instance of the API collector that where we will save the API information
        """
        count = 0
        for _, event in serverless_function_events.items():

            if self._FUNCTION_EVENT_TYPE_ROUTE == event.get(self._EVENT_TYPE):
                api_resource_id, routes = self._convert_event_route(function_logical_id, event.get("Properties"))
                collector.add_routes(api_resource_id, routes)
                count += 1

        LOG.debug("Found '%d' API Events in Serverless function with name '%s'", count, function_logical_id)

    @staticmethod
    def _convert_event_route(lambda_logical_id, event_properties):
        """
        Converts a AWS::Serverless::Function's Event Property to an Api configuration usable by the provider.

        :param str lambda_logical_id: Logical Id of the AWS::Serverless::Function
        :param dict event_properties: Dictionary of the Event's Property
        :return tuple: tuple of API resource name and Api namedTuple
        """
        path = event_properties.get(FunctionParserProvider._EVENT_PATH)
        method = event_properties.get(FunctionParserProvider._EVENT_METHOD)

        # An API Event, can have RestApiId property which designates the resource that owns this API. If omitted,
        # the API is owned by Implicit API resource. This could either be a direct resource logical ID or a
        # "Ref" of the logicalID
        resource_id = event_properties.get("RestApiId", ApiProvider.IMPLICIT_API_RESOURCE_ID)
        if isinstance(resource_id, dict) and "Ref" in resource_id:
            resource_id = resource_id["Ref"]
        routes = Route.get_normalized_routes(function_name=lambda_logical_id, path=path, method=method)
        return resource_id, routes


class SAMAParserApiProvider(AbstractParserProvider):
    RESOURCE_TYPE = "AWS::Serverless::Api"
    PROVIDER_TYPE = ApiProvider.PROVIDER_TYPE_CLOUD_FORMATION

    def extract_route(self, logical_id, api_resource, collector, api, cwd=None):
        return self._extract_from_serverless_api(logical_id, api_resource, collector, api, cwd)

    def _extract_from_serverless_api(self, logical_id, api_resource, collector, api, cwd=None):
        """
        Extract APIs from AWS::Serverless::Api resource by reading and parsing Swagger documents. The result is added
        to the collector.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        api : Api
            Resource definition, including its properties

        collector : RouteCollector
            Instance of the API collector that where we will save the API information
        """

        properties = api_resource.get("Properties", {})
        body = properties.get("DefinitionBody")
        uri = properties.get("DefinitionUri")
        binary_media = properties.get("BinaryMediaTypes", [])
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")

        if not body and not uri:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in DefinitionBody and DefinitionUri",
                      logical_id)
            return
        self.extract_swagger_routes(logical_id, body, uri, binary_media, collector, api, cwd)
        api.stage_name = stage_name
        api.stage_variables = stage_variables


class CFParserApiProvider(AbstractParserProvider):
    RESOURCE_TYPE = "AWS::ApiGateway::RestApi"
    PROVIDER_TYPE = ApiProvider.PROVIDER_TYPE_CLOUD_FORMATION

    def extract_route(self, logical_id, api_resource, collector, api, cwd=None):
        return self._extract_cloud_formation_api(logical_id, api_resource, collector, api, cwd)

    def _extract_cloud_formation_api(self, logical_id, api_resource, collector, api, cwd=None):
        """
        Extract APIs from AWS::ApiGateway::RestApi resource by reading and parsing Swagger documents. The result is
        added to the collector.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        api_resource : dict
            Resource definition, including its properties

        collector : RouteCollector
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
        self.extract_swagger_routes(logical_id, body, s3_location, binary_media, collector, api, cwd)


class CFParserStageProvider(AbstractParserProvider):
    RESOURCE_TYPE = "AWS::ApiGateway::Stage"
    PROVIDER_TYPE = ApiProvider.PROVIDER_TYPE_CLOUD_FORMATION

    def extract_route(self, logical_id, api_resource, collector, api, cwd=None):
        return self._extract_cloud_formation_stage(api_resource, api)

    def _extract_cloud_formation_stage(self, api_resource, api):
        """
        Extract APIs from AWS::ApiGateway::Stage resource by reading and adds it to the collector.
        Parameters
       ----------
        logical_id : str
            Logical ID of the resource
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
