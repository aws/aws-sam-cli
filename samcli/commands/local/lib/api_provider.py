"""Class that provides the Api with a list of routes from a Template"""

import logging

from samcli.commands.local.lib.cf_api_provider import CFApiProvider
from samcli.commands.local.lib.provider import AbstractApiProvider, Api
from samcli.commands.local.lib.route_collector import RouteCollector
from samcli.commands.local.lib.sam_api_provider import SamApiProvider
from samcli.commands.local.lib.sam_base_provider import SamBaseProvider
from samcli.local.apigw.local_apigw_service import Route

LOG = logging.getLogger(__name__)


class ApiProvider(AbstractApiProvider):
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
        self.api.routes = self.routes
        LOG.debug("%d APIs found in the template", len(self.routes))

    def get_all(self):
        """
        Yields all the Lambda functions with Api Events available in the Template.

        :yields route: namedtuple containing the Api information
        """

        for route in self.routes:
            yield route

    def _extract_routes(self, resources):
        """
        Extracts all the Routes by running through the different providers. The different providers parse the output and
        the relevant routes to the collector

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template
        Returns
        ---------
        list of routes extracted from the resources
        """
        collector = RouteCollector()
        # the template we are creating the implicit apis due to plugins that translate it in the SAM repo,
        # which we later merge with the explicit ones in SamApiProvider.merge_routes. This requires the code to be
        # parsed here and in InvokeContext.

        providers = {SamApiProvider.SERVERLESS_API: SamApiProvider(),
                     SamApiProvider.SERVERLESS_FUNCTION: SamApiProvider(),
                     CFApiProvider.APIGATEWAY_RESTAPI: CFApiProvider(),
                     CFApiProvider.APIGATEWAY_STAGE: CFApiProvider()}
        for logical_id, resource in resources.items():
            resource_type = resource.get(self._TYPE)
            providers.get(resource_type, SamApiProvider()) \
                .extract_resource(resource_type, logical_id, resource, collector, self.api,
                                  cwd=self.cwd)
        routes = SamApiProvider.merge_routes(collector)
        return Route.normalize_routes(routes)
