"""Class that provides Apis from a SAM Template"""

import logging
from collections import namedtuple

from six import string_types

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.commands.local.lib.provider import ApiProvider, Api
from samcli.commands.local.lib.sam_base_provider import SamBaseProvider
from samcli.commands.local.lib.swagger.reader import SamSwaggerReader
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

LOG = logging.getLogger(__name__)


class SamApiProvider(ApiProvider):

    _IMPLICIT_API_RESOURCE_ID = "ServerlessRestApi"
    _SERVERLESS_FUNCTION = "AWS::Serverless::Function"
    _SERVERLESS_API = "AWS::Serverless::Api"
    _TYPE = "Type"

    _FUNCTION_EVENT_TYPE_API = "Api"
    _FUNCTION_EVENT = "Events"
    _EVENT_PATH = "Path"
    _EVENT_METHOD = "Method"

    _ANY_HTTP_METHODS = ["GET",
                         "DELETE",
                         "PUT",
                         "POST",
                         "HEAD",
                         "OPTIONS",
                         "PATCH"]

    def __init__(self, template_dict, parameter_overrides=None, cwd=None):
        """
        Initialize the class with SAM template data. The template_dict (SAM Templated) is assumed
        to be valid, normalized and a dictionary. template_dict should be normalized by running any and all
        pre-processing before passing to this class.
        This class does not perform any syntactic validation of the template.

        After the class is initialized, changes to ``template_dict`` will not be reflected in here.
        You will need to explicitly update the class with new template, if necessary.

        Parameters
        ----------
        template_dict : dict
            SAM Template as a dictionary
        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file
        """

        self.template_dict = SamBaseProvider.get_template(template_dict, parameter_overrides)
        self.resources = self.template_dict.get("Resources", {})

        LOG.debug("%d resources found in the template", len(self.resources))

        # Store a set of apis
        self.cwd = cwd
        self.apis = self._extract_apis(self.resources)

        LOG.debug("%d APIs found in the template", len(self.apis))

    def get_all(self):
        """
        Yields all the Lambda functions with Api Events available in the SAM Template.

        :yields Api: namedtuple containing the Api information
        """

        for api in self.apis:
            yield api

    def _extract_apis(self, resources):
        """
        Extract all Implicit Apis (Apis defined through Serverless Function with an Api Event

        :param dict resources: Dictionary of SAM/CloudFormation resources
        :return: List of nametuple Api
        """

        # Some properties like BinaryMediaTypes, Cors are set once on the resource but need to be applied to each API.
        # For Implicit APIs, which are defined on the Function resource, these properties
        # are defined on a AWS::Serverless::Api resource with logical ID "ServerlessRestApi". Therefore, no matter
        # if it is an implicit API or an explicit API, there is a corresponding resource of type AWS::Serverless::Api
        # that contains these additional configurations.
        #
        # We use this assumption in the following loop to collect information from resources of type
        # AWS::Serverless::Api. We also extract API from Serverless::Function resource and add them to the
        # corresponding Serverless::Api resource. This is all done using the ``collector``.

        collector = ApiCollector()

        for logical_id, resource in resources.items():

            resource_type = resource.get(SamApiProvider._TYPE)

            if resource_type == SamApiProvider._SERVERLESS_FUNCTION:
                self._extract_apis_from_function(logical_id, resource, collector)

            if resource_type == SamApiProvider._SERVERLESS_API:
                self._extract_from_serverless_api(logical_id, resource, collector)

        apis = SamApiProvider._merge_apis(collector)
        return self._normalize_apis(apis)

    def _extract_from_serverless_api(self, logical_id, api_resource, collector):
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

        if not body and not uri:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in DefinitionBody and DefinitionUri",
                      logical_id)
            return

        reader = SamSwaggerReader(definition_body=body,
                                  definition_uri=uri,
                                  working_dir=self.cwd)
        swagger = reader.read()
        parser = SwaggerParser(swagger)
        apis = parser.get_apis()
        LOG.debug("Found '%s' APIs in resource '%s'", len(apis), logical_id)

        collector.add_apis(logical_id, apis)
        collector.add_binary_media_types(logical_id, parser.get_binary_media_types())  # Binary media from swagger
        collector.add_binary_media_types(logical_id, binary_media)  # Binary media specified on resource in template

    @staticmethod
    def _merge_apis(collector):
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
            if logical_id == SamApiProvider._IMPLICIT_API_RESOURCE_ID:
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
            for normalized_method in SamApiProvider._normalize_http_methods(config.method):
                key = config.path + normalized_method
                all_apis[key] = config

        result = set(all_apis.values())  # Assign to a set() to de-dupe
        LOG.debug("Removed duplicates from '%d' Explicit APIs and '%d' Implicit APIs to produce '%d' APIs",
                  len(explicit_apis), len(implicit_apis), len(result))

        return list(result)

    @staticmethod
    def _normalize_apis(apis):
        """
        Normalize the APIs to use standard method name

        Parameters
        ----------
        apis : list of samcli.commands.local.lib.provider.Api
            List of APIs to replace normalize

        Returns
        -------
        list of samcli.commands.local.lib.provider.Api
            List of normalized APIs
        """

        result = list()
        for api in apis:
            for normalized_method in SamApiProvider._normalize_http_methods(api.method):
                # _replace returns a copy of the namedtuple. This is the official way of creating copies of namedtuple
                result.append(api._replace(method=normalized_method))

        return result

    @staticmethod
    def _extract_apis_from_function(logical_id, function_resource, collector):
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
        serverless_function_events = resource_properties.get(SamApiProvider._FUNCTION_EVENT, {})
        SamApiProvider._extract_apis_from_events(logical_id, serverless_function_events, collector)

    @staticmethod
    def _extract_apis_from_events(function_logical_id, serverless_function_events, collector):
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

            if SamApiProvider._FUNCTION_EVENT_TYPE_API == event.get(SamApiProvider._TYPE):
                api_resource_id, api = SamApiProvider._convert_event_api(function_logical_id, event.get("Properties"))
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
        api_resource_id = event_properties.get("RestApiId", SamApiProvider._IMPLICIT_API_RESOURCE_ID)
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
    def _normalize_http_methods(http_method):
        """
        Normalizes Http Methods. Api Gateway allows a Http Methods of ANY. This is a special verb to denote all
        supported Http Methods on Api Gateway.

        :param str http_method: Http method
        :yield str: Either the input http_method or one of the _ANY_HTTP_METHODS (normalized Http Methods)
        """

        if http_method.upper() == 'ANY':
            for method in SamApiProvider._ANY_HTTP_METHODS:
                yield method.upper()
        else:
            yield http_method.upper()


class ApiCollector(object):
    """
    Class to store the API configurations in the SAM Template. This class helps store both implicit and explicit
    APIs in a standardized format
    """

    # Properties of each API. The structure is quite similar to the properties of AWS::Serverless::Api resource.
    # This is intentional because it allows us to easily extend this class to support future properties on the API.
    # We will store properties of Implicit APIs also in this format which converges the handling of implicit & explicit
    # APIs.
    Properties = namedtuple("Properties", ["apis", "binary_media_types", "cors"])

    def __init__(self):
        # API properties stored per resource. Key is the LogicalId of the AWS::Serverless::Api resource and
        # value is the properties
        self.by_resource = {}

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
            yield logical_id, self._get_apis_with_config(logical_id)

    def add_apis(self, logical_id, apis):
        """
        Stores the given APIs tagged under the given logicalId

        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        apis : list of samcli.commands.local.lib.provider.Api
            List of APIs available in this resource
        """
        properties = self._get_properties(logical_id)
        properties.apis.extend(apis)

    def add_binary_media_types(self, logical_id, binary_media_types):
        """
        Stores the binary media type configuration for the API with given logical ID

        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        binary_media_types : list of str
            List of binary media types supported by this resource

        """
        properties = self._get_properties(logical_id)

        binary_media_types = binary_media_types or []
        for value in binary_media_types:
            normalized_value = self._normalize_binary_media_type(value)

            # If the value is not supported, then just skip it.
            if normalized_value:
                properties.binary_media_types.add(normalized_value)
            else:
                LOG.debug("Unsupported data type of binary media type value of resource '%s'", logical_id)

    def _get_apis_with_config(self, logical_id):
        """
        Returns the list of APIs in this resource along with other extra configuration such as binary media types,
        cors etc. Additional configuration is merged directly into the API data because these properties, although
        defined globally, actually apply to each API.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource to fetch data for

        Returns
        -------
        list of samcli.commands.local.lib.provider.Api
            List of APIs with additional configurations for the resource with given logicalId. If there are no APIs,
            then it returns an empty list
        """

        properties = self._get_properties(logical_id)

        # These configs need to be applied to each API
        binary_media = sorted(list(properties.binary_media_types))  # Also sort the list to keep the ordering stable
        cors = properties.cors

        result = []
        for api in properties.apis:
            # Create a copy of the API with updated configuration
            updated_api = api._replace(binary_media_types=binary_media,
                                       cors=cors)
            result.append(updated_api)

        return result

    def _get_properties(self, logical_id):
        """
        Returns the properties of resource with given logical ID. If a resource is not found, then it returns an
        empty data.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        Returns
        -------
        samcli.commands.local.lib.sam_api_provider.ApiCollector.Properties
            Properties object for this resource.
        """

        if logical_id not in self.by_resource:
            self.by_resource[logical_id] = self.Properties(apis=[],
                                                           # Use a set() to be able to easily de-dupe
                                                           binary_media_types=set(),
                                                           cors=None)

        return self.by_resource[logical_id]

    @staticmethod
    def _normalize_binary_media_type(value):
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
