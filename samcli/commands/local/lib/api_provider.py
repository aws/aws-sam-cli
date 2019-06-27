"""Class that provides Apis from a SAM Template"""

import logging

from samcli.commands.local.lib.api_collector import ApiCollector
from samcli.commands.local.lib.cf_api_provider import CFApiProvider
from samcli.commands.local.lib.provider import AbstractApiProvider
from samcli.commands.local.lib.sam_base_provider import SamBaseProvider
from samcli.commands.local.lib.sam_api_provider import SamApiProvider

LOG = logging.getLogger(__name__)


class ApiProvider(AbstractApiProvider):
    _TYPE = "Type"

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
        Extracts all the Apis by running through the different providers. The different providers parse the output and
        the relevant Apis to the collector

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template
        Returns
        ---------
        list of Apis extracted from the resources
        """
        collector = ApiCollector()
        # AWS::Serverless::Function is currently included when parsing of Apis because when SamBaseProvider is run on
        # the template we are creating the implicit apis due to plugins that translate it in the SAM repo,
        # which we later merge with the explicit ones in SamApiProvider.merge_apis. This requires the code to be
        # parsed here and in InvokeContext.

        providers = {SamApiProvider.SERVERLESS_API: SamApiProvider(),
                     SamApiProvider.SERVERLESS_FUNCTION: SamApiProvider(),
                     CFApiProvider.APIGATEWAY_RESTAPI: CFApiProvider()}
        for logical_id, resource in resources.items():
            resource_type = resource.get(self._TYPE)
            providers.get(resource_type, SamApiProvider()) \
                .extract_resource_api(resource_type, logical_id, resource, collector,
                                      cwd=self.cwd)
        apis = SamApiProvider.merge_apis(collector)
        return self.normalize_apis(apis)
