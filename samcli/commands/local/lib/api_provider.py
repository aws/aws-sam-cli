"""Class that provides the Api with a list of routes from a Template"""

import logging

from samcli.commands.local.lib.route_collector import RouteCollector
from samcli.commands.local.lib.cf_base_api_provider import CFBaseApiProvider
from samcli.commands.local.lib.provider import AbstractApiProvider, Api
from samcli.commands.local.lib.sam_base_provider import SamBaseProvider
from samcli.commands.local.lib.sam_api_provider import SamApiProvider
from samcli.commands.local.lib.cf_api_provider import CFApiProvider

LOG = logging.getLogger(__name__)


class ApiProvider(AbstractApiProvider):

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
        Yields all the Lambda functions with Routes Events available in the Template.

        :yields route: namedtuple containing the Route information
        """

        for route in self.routes:
            yield route

    def _extract_routes(self, resources):
        """
        Extracts all the routes by running through the one providers. The provider that has the first type matched
        will be run across all the resources

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template
        Returns
        ---------
        list of routes extracted from the resources
        """
        collector = RouteCollector()
        provider = self.find_correct_api_provider(resources)
        routes = provider.extract_resources(resources, collector, api=self.api, cwd=self.cwd)
        return self.normalize_routes(routes)

    @staticmethod
    def find_correct_api_provider(resources):
        """
        Finds the correct ApiProvider given the type of the first resource

        Parameters
        -----------
        resources: dict
            The dictionary containing the different resources within the template

        Return
        ----------
        Instance of the ApiProvider that will be run on the template
        :return:
        """
        for _, resource in resources.items():
            if resource.get(CFBaseApiProvider.RESOURCE_TYPE) in SamApiProvider.TYPES:
                return SamApiProvider()
            elif resource.get(CFBaseApiProvider.RESOURCE_TYPE) in CFApiProvider.TYPES:
                return CFApiProvider()

        return SamApiProvider()
