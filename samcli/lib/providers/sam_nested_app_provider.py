"""
Class that provides nested applications from a given SAM template
"""
import logging
from typing import NamedTuple, Optional, Any
from urllib.parse import unquote, urlparse

from samcli.lib.utils.colors import Colored
from .sam_base_provider import SamBaseProvider
from ...commands._utils.template import get_template_data

LOG = logging.getLogger(__name__)


class Application(NamedTuple):
    app_prefix: str
    name: str
    location: str
    parameters: Optional[Any]


class SamNestedAppProvider(SamBaseProvider):
    """
    Fetches and returns nested application from a SAM Template. The SAM template passed to this provider is assumed
    to be valid, normalized and a dictionary.
    It may or may not contain an application.
    """

    def __init__(self, app_prefix: str, template_file: str, parameter_overrides=None, base_url=None):
        """
        Initialize the class with SAM template data. The SAM template passed to this provider is assumed
        to be valid, normalized and a dictionary. It should be normalized by running all pre-processing
        before passing to this class. The process of normalization will remove structures like ``Globals``, resolve
        intrinsic functions etc.
        This class does not perform any syntactic validation of the template.
        After the class is initialized, any changes to the ``template_dict`` will not be reflected in here.
        You need to explicitly update the class with new template, if necessary.
        :param dict template_dict: SAM Template as a dictionary
        :param dict parameter_overrides: Optional dictionary of values for SAM template parameters that might want
            to get substituted within the template
        """

        self.app_prefix = app_prefix
        self.template_file = template_file
        template_dict = get_template_data(template_file)
        self.template_dict = SamNestedAppProvider.get_template(template_dict, parameter_overrides)
        self.resources = self.template_dict.get("Resources", {})
        self.base_url = base_url

        LOG.debug("%d resources found in the template", len(self.resources))

        # Store a map of function name to function information for quick reference
        self.applications = self._extract_applications()

        self._colored = Colored()

    def get(self, name):
        """
        Returns the application given name or LogicalId of the application.
        Every SAM resource has a logicalId, but it may
        also have a application name. This method searches only for LogicalID and returns the application that matches
        it.
        :param string name: Name of the application
        :return Function: namedtuple containing the Application information if application is found.
                          None, if application is not found
        :raises ValueError If name is not given
        """

        if not name:
            raise ValueError("Application name is required")

        for f in self.get_all():
            if f.name == name:
                return f

        return None

    def get_all(self):
        """
        Yields all the applications available in the SAM Template.
        :yields Application: map containing the application information
        """

        for _, application in self.applications.items():
            yield application

    def _extract_applications(self):
        """
        Extracts and returns nested application information from the given dictionary of SAM/CloudFormation resources.
        This method supports applications defined with AWS::Serverless::Application
        :return dict(string : application): Dictionary of application LogicalId to the
            Application object
        """

        result = {}

        for name, resource in self.resources.items():

            resource_type = resource.get("Type")
            resource_properties = resource.get("Properties", {})
            resource_metadata = resource.get("Metadata", None)
            # Add extra metadata information to properties under a separate field.
            if resource_metadata:
                resource_properties["Metadata"] = resource_metadata

            if resource_type == SamNestedAppProvider.SERVERLESS_APPLICATION and not resource_properties.get(
                "Location"
            ).startswith("s3://"):
                result[name] = SamNestedAppProvider._convert_sam_application_resource(
                    self.app_prefix, name, resource_properties
                )

            if resource_type == SamNestedAppProvider.CLOUDFORMATION_STACK and resource_properties.get(
                "TemplateURL"
            ).startswith("file://"):
                result[name] = SamNestedAppProvider._convert_sam_application_resource(
                    self.app_prefix, name, resource_properties
                )

            # We don't care about other resource types. Just ignore them

        return result

    @staticmethod
    def _convert_sam_application_resource(app_prefix, name, resource_properties):
        location = resource_properties.get("Location")
        if location.startswith("file://"):
            location = unquote(urlparse(location).path)
        return Application(
            app_prefix=app_prefix, name=name, location=location, parameters=resource_properties.get("Parameters")
        )

    @staticmethod
    def _convert_cfn_stack_resource(app_prefix, name, resource_properties):
        location = unquote(urlparse(resource_properties.get("TemplateURL")).path)
        return Application(
            app_prefix=app_prefix, name=name, location=location, parameters=resource_properties.get("Parameters")
        )
