"""
Class that provides all nested stacks from a given SAM template
"""
import logging
import os
from typing import Optional, Dict, cast, List, Iterator
from urllib.parse import unquote, urlparse

from samcli.commands._utils.template import get_template_data
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_base_provider import SamBaseProvider

LOG = logging.getLogger(__name__)


class SamLocalStackProvider(SamBaseProvider):
    """
    Fetches and returns local nested stacks from a SAM Template. The SAM template passed to this provider is assumed
    to be valid, normalized and a dictionary.
    It may or may not contain a stack.
    """

    # see get_stacks() for info about this env var
    ENV_SAM_CLI_ENABLE_NESTED_STACK = "SAM_CLI_ENABLE_NESTED_STACK"

    def __init__(self, stack_path: str, template_dict: Dict, parameter_overrides: Optional[Dict] = None):
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

        self._stack_path = stack_path
        self._template_dict = self.get_template(template_dict, parameter_overrides)
        self._resources = self._template_dict.get("Resources", {})

        LOG.debug("%d stacks found in the template", len(self._resources))

        # Store a map of stack name to stack information for quick reference
        self._stacks = self._extract_stacks()

    def get(self, name: str) -> Optional[Stack]:
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
        for f in self.get_all():
            if f.name == name:
                return f

        return None

    def get_all(self) -> Iterator[Stack]:
        """
        Yields all the applications available in the SAM Template.
        :yields Application: map containing the application information
        """

        for _, stack in self._stacks.items():
            yield stack

    def _extract_stacks(self) -> Dict[str, Stack]:
        """
        Extracts and returns nested application information from the given dictionary of SAM/CloudFormation resources.
        This method supports applications defined with AWS::Serverless::Application
        :return dict(string : application): Dictionary of application LogicalId to the
            Application object
        """

        result: Dict[str, Stack] = {}

        for name, resource in self._resources.items():

            resource_type = resource.get("Type")
            resource_properties = resource.get("Properties", {})
            resource_metadata = resource.get("Metadata", None)
            # Add extra metadata information to properties under a separate field.
            if resource_metadata:
                resource_properties["Metadata"] = resource_metadata

            stack: Optional[Stack] = None
            if resource_type == SamLocalStackProvider.SERVERLESS_APPLICATION:
                stack = SamLocalStackProvider._convert_sam_application_resource(
                    self._stack_path, name, resource_properties
                )
            if resource_type == SamLocalStackProvider.CLOUDFORMATION_STACK:
                stack = SamLocalStackProvider._convert_cfn_stack_resource(self._stack_path, name, resource_properties)

            if stack:
                result[name] = stack

            # We don't care about other resource types. Just ignore them

        return result

    @staticmethod
    def _convert_sam_application_resource(stack_path: str, name: str, resource_properties: Dict) -> Optional[Stack]:
        location = resource_properties.get("Location")

        if isinstance(location, dict):
            LOG.warning(
                "Nested application '%s' has specified an application published to the "
                "AWS Serverless Application Repository which is unsupported. "
                "Skipping resources inside this nested application.",
                name,
            )
            return None

        location = cast(str, location)
        if SamLocalStackProvider.is_remote_url(location):
            LOG.warning(
                "Nested application '%s' has specified S3 location for Location which is unsupported. "
                "Skipping resources inside this nested application.",
                name,
            )
            return None
        if location.startswith("file://"):
            location = unquote(urlparse(location).path)

        return Stack(
            parent_stack_path=stack_path,
            name=name,
            location=location,
            parameters=resource_properties.get("Parameters"),
            template_dict=get_template_data(location),
        )

    @staticmethod
    def _convert_cfn_stack_resource(stack_path: str, name: str, resource_properties: Dict) -> Optional[Stack]:
        template_url = resource_properties.get("TemplateURL", "")

        if SamLocalStackProvider.is_remote_url(template_url):
            LOG.warning(
                "Nested stack '%s' has specified S3 location for Location which is unsupported. "
                "Skipping resources inside this nested stack.",
                name,
            )
            return None
        if template_url.startswith("file://"):
            template_url = unquote(urlparse(template_url).path)

        return Stack(
            parent_stack_path=stack_path,
            name=name,
            location=template_url,
            parameters=resource_properties.get("Parameters"),
            template_dict=get_template_data(template_url),
        )

    @staticmethod
    def get_stacks(
        template_file: str,
        stack_path: str = "",
        name: str = "",
        parameter_overrides: Optional[Dict] = None,
    ) -> List[Stack]:
        template_dict = get_template_data(template_file)
        stacks = [Stack(stack_path, name, template_file, parameter_overrides, template_dict)]

        # Note(xinhol): recursive get_stacks is only enabled in tests by env var SAM_CLI_ENABLE_NESTED_STACK.
        # We will remove this env var and make this method recursive by default
        # for nested stack support in the future.
        if not os.environ.get(SamLocalStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK, False):
            return stacks

        current = SamLocalStackProvider(stack_path, template_dict, parameter_overrides)
        for child_stack in current.get_all():
            stacks.extend(
                SamLocalStackProvider.get_stacks(
                    child_stack.location,
                    os.path.join(stack_path, name),
                    child_stack.name,
                    child_stack.parameters,
                )
            )
        return stacks

    @staticmethod
    def is_remote_url(url: str):
        return any([url.startswith(prefix) for prefix in ["s3://", "http://", "https://"]])

    @staticmethod
    def find_root_stack(stacks: List[Stack]) -> Stack:
        candidates = [stack for stack in stacks if stack.is_root_stack]
        if not candidates:
            stacks_str = ", ".join([stack.stack_path for stack in stacks])
            raise ValueError(f"{stacks_str} does not contain a root stack")
        return candidates[0]
