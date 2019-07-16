"""Class that provides Apis from a SAM Template"""

import logging

from samcli.commands.local.lib.cfn_base_api_provider import CfnBaseApiProvider
from samcli.commands.local.lib.api_collector import ApiCollector
from samcli.commands.local.lib.provider import AbstractApiProvider
from samcli.commands.local.lib.sam_base_provider import SamBaseProvider
from samcli.commands.local.lib.sam_api_provider import SamApiProvider
from samcli.commands.local.lib.cfn_api_provider import CfnApiProvider

LOG = logging.getLogger(__name__)


class ApiProvider(AbstractApiProvider):

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
        Extracts all the Apis by running through the one providers. The provider that has the first type matched
        will be run across all the resources

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template
        Returns
        ---------
        list of Apis extracted from the resources
        """
        collector = ApiCollector()
        provider = self.find_api_provider(resources)
        apis = provider.extract_resource_api(resources, collector, cwd=self.cwd)
        return self.normalize_apis(apis)

    @staticmethod
    def find_api_provider(resources):
        """
        Finds the ApiProvider given the first api type of the resource

        Parameters
        -----------
        resources: dict
            The dictionary containing the different resources within the template

        Return
        ----------
        Instance of the ApiProvider that will be run on the template with a default of SamApiProvider
        """
        for _, resource in resources.items():
            if resource.get(CfnBaseApiProvider.RESOURCE_TYPE) in SamApiProvider.TYPES:
                return SamApiProvider()
            elif resource.get(CfnBaseApiProvider.RESOURCE_TYPE) in CfnApiProvider.TYPES:
                return CfnApiProvider()

        return SamApiProvider()
