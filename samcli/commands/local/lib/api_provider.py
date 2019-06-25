from commands.local.lib.provider import ApiProvider
from commands.local.lib.sam_api_provider import ApiCollector, SamApiProvider
from commands.local.lib.sam_base_provider import SamBaseProvider, LOG
from commands.local.lib.swagger.parser import SwaggerParser
from commands.local.lib.swagger.reader import SamSwaggerReader


class AbstractApiProvider(ApiProvider):
    _IMPLICIT_API_RESOURCE_ID = "ServerlessRestApi"
    _SERVERLESS_FUNCTION = "AWS::Serverless::Function"
    _SERVERLESS_API = "AWS::Serverless::Api"
    _GATEWAY_REST_API = "AWS::ApiGateway::RestApi"
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
    PROVIDER_TYPE_CF = "CF"

    def __init__(self, template_dict, api_provider=SamBaseProvider, parameter_overrides=None, cwd=None,
                 provider_type="CF"):
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
        self.provider_type = provider_type
        if self.provider_type == AbstractApiProvider.PROVIDER_TYPE_CF:
            self.template_dict = api_provider.get_template(template_dict, parameter_overrides)
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
        providers = {provider.RESOURCE_TYPE: provider for provider in ParserApiProvider.__subclasses__() if
                     provider.PROVIDER_TYPE == self.provider_type}
        for logical_id, resource in resources.items():
            resource_type = resource.get(SamApiProvider._TYPE)
            provider = providers.get(resource_type)
            if provider:
                provider.extract_api(logical_id, resource, collector)
        apis = SamApiProvider._merge_apis(collector)
        return self._normalize_apis(apis)


class ParserApiProvider(object):

    def extract_api(self, logical_id, api_resource, collector, cwd=None):
        pass

    def get_type(self):
        pass

    def _extract_swagger_api(self, logical_id, body, uri, binary_media, collector, cwd=None):
        """
        Parse the Swagger documents given the Api properties.

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


class FunctionProvider(ParserApiProvider):
    RESOURCE_TYPE = "AWS::Serverless::Function"
    PROVIDER_TYPE = AbstractApiProvider.PROVIDER_TYPE_CF

    def extract_api(self, logical_id, api_resource, collector, cwd=None):
        return self._extract_apis_from_function(logical_id, api_resource, collector)

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


class SAMApiProvider(ParserApiProvider):
    RESOURCE_TYPE = "AWS::Serverless::Api"
    PROVIDER_TYPE = AbstractApiProvider.PROVIDER_TYPE_CF

    def extract_api(self, logical_id, api_resource, collector, cwd=None):
        return self._extract_from_serverless_api(logical_id, api_resource, collector, cwd)

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
        stage_name = properties.get("StageName")
        stage_variables = properties.get("Variables")

        if not body and not uri:
            # Swagger is not found anywhere.
            LOG.debug("Skipping resource '%s'. Swagger document not found in DefinitionBody and DefinitionUri",
                      logical_id)
            return
        self._extract_swagger_api(logical_id, body, uri, binary_media, collector, cwd)
        collector.add_stage_name(logical_id, stage_name)
        collector.add_stage_variables(logical_id, stage_variables)


class CFNApiProvider(ParserApiProvider):
    RESOURCE_TYPE = "AWS::ApiGateway::RestApi"
    PROVIDER_TYPE = AbstractApiProvider.PROVIDER_TYPE_CF

    def extract_api(self, logical_id, api_resource, collector, cwd=None):
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
        self._extract_swagger_api(logical_id, body, s3_location, binary_media, collector, cwd)
