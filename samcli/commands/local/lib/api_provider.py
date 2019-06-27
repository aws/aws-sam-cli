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

    def __init__(self, template_dict, parameter_overrides=None, cwd=None):
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
        """
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

        for route in self.routes:
            yield route

    def _extract_routes(self, resources):
        collector = RouteCollector()
        providers = {SamApiProvider.SERVERLESS_API: SamApiProvider(),
                     SamApiProvider.SERVERLESS_FUNCTION: SamApiProvider(),
                     CFApiProvider.APIGATEWAY_RESTAPI: CFApiProvider()}
        for logical_id, resource in resources.items():
            resource_type = resource.get(self._TYPE)
            providers.get(resource_type, SamApiProvider()) \
                .extract_resource_route(resource_type, logical_id, resource, collector, self.api,
                                        cwd=self.cwd)
        apis = self._merge_apis(collector)
        return self._normalize_apis(apis)

    @staticmethod
    def _normalize_http_methods(http_method):
        """
        Normalizes Http Methods. Api Gateway allows a Http Methods of ANY. This is a special verb to denote all
        supported Http Methods on Api Gateway.

        :param str http_method: Http method
        :yield str: Either the input http_method or one of the _ANY_HTTP_METHODS (normalized Http Methods)
        """

        if http_method.upper() == 'ANY':
            for method in Route.ANY_HTTP_METHODS:
                yield method.upper()
        else:
            yield http_method.upper()

    @staticmethod
    def _normalize_apis(routes):
        """
        Normalize the APIs to use standard method name

        Parameters
        ----------
        apis : list of local.apigw.local_apigw_service.Route
            List of Routes to replace normalize

        Returns
        -------
        list of local.apigw.local_apigw_service.Route
            List of normalized Routes
        """

        for route in routes:
            for normalized_method in ApiProvider._normalize_http_methods(route.method):
                # _replace returns a copy of the namedtuple. This is the official way of creating copies of namedtuple
                route.method = normalized_method
        return routes

    @staticmethod
    def _merge_apis(collector):
        """
        Quite often, an API is defined both in Implicit and Explicit API definitions. In such cases, Implicit API
        definition wins because that conveys clear intent that the API is backed by a function. This method will
        merge two such list of Apis with the right order of precedence. If a Path+Method combination is defined
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


class CFBaseApiProvider(object):

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
        collector: ApiCollector
            Instance of the API collector that where we will save the API information
        api: Api
            Instace of Api object to hold the properties
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
        api.binary_media_types_set.add(parser.get_binary_media_types())  # Binary media from swagger
        api.binary_media_types_set.add(binary_media)  # Binary media specified on resource in template

    def extract_resource_route(self, resource_type, logical_id, api_resource, collector, api, cwd=None):
        raise NotImplementedError("not implemented")


class SamApiProvider(CFBaseApiProvider):
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

    def extract_resource_route(self, resource_type, logical_id, api_resource, collector, api, cwd=None):
        """
        Extract the Api Object from a given resource and adds it to the ApiCollector.

        Parameters
        ----------
        resource_type: str
            The resource property type
        logical_id : str
            Logical ID of the resource

        api_resource: dict
            Contents of the function resource including its properties\

        collector: ApiCollector
            Instance of the API collector that where we will save the API information

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file


        """
        if resource_type == SamApiProvider.SERVERLESS_FUNCTION:
            return self._extract_apis_from_function(logical_id, api_resource, collector)

        if resource_type == SamApiProvider.SERVERLESS_API:
            return self._extract_from_serverless_api(logical_id, api_resource, collector, api, cwd)

    def _extract_from_serverless_api(self, logical_id, api_resource, collector, api, cwd=None):
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
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")

        if not body and not uri:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in DefinitionBody and DefinitionUri",
                      logical_id)
            return
        self.extract_swagger_routes(logical_id, body, uri, binary_media, collector, cwd)
        api.stage_name = stage_name
        api.stage_variables = stage_variables

    def _extract_apis_from_function(self, logical_id, function_resource, collector):
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

            if self._FUNCTION_EVENT_TYPE_API == event.get(self._EVENT_TYPE):
                api_resource_id, route = self._convert_event_route(function_logical_id, event.get("Properties"))
                collector.add_routes(api_resource_id, [route])
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
        path = event_properties.get(SamApiProvider._EVENT_PATH)
        method = event_properties.get(SamApiProvider._EVENT_METHOD)

        # An API Event, can have RestApiId property which designates the resource that owns this API. If omitted,
        # the API is owned by Implicit API resource. This could either be a direct resource logical ID or a
        # "Ref" of the logicalID
        api_resource_id = event_properties.get("RestApiId", ApiProvider.IMPLICIT_API_RESOURCE_ID)
        if isinstance(api_resource_id, dict) and "Ref" in api_resource_id:
            api_resource_id = api_resource_id["Ref"]

        return api_resource_id, Route(path=path, method=method, function_name=lambda_logical_id)


class CFApiProvider(CFBaseApiProvider):
    APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
    APIGATEWAY_STAGE = "AWS::ApiGateway::Stage"
    TYPES = [
        APIGATEWAY_RESTAPI,
        APIGATEWAY_STAGE
    ]

    def extract_resource_route(self, resource_type, logical_id, api_resource, collector, api, cwd=None):
        if resource_type == CFApiProvider.APIGATEWAY_RESTAPI:
            return self._extract_cloud_formation_api(logical_id, api_resource, collector, api, cwd)

        if resource_type == CFApiProvider.APIGATEWAY_STAGE:
            return self._extract_cloud_formation_stage(api_resource, api)

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

    @staticmethod
    def _extract_cloud_formation_stage(api_resource, api):
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
