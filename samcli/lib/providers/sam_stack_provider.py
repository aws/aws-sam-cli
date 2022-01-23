"""
Class that provides all nested stacks from a given SAM template
"""
import logging
import os
from typing import Optional, Dict, cast, List, Iterator, Tuple, Union
from urllib.parse import unquote, urlparse

from samcli.commands._utils.template import get_template_data
from samcli.lib.providers.exceptions import RemoteStackLocationNotSupported
from samcli.lib.providers.provider import Stack, get_full_path
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.utils.resources import AWS_CLOUDFORMATION_STACK, AWS_SERVERLESS_APPLICATION

LOG = logging.getLogger(__name__)


class SamLocalStackProvider(SamBaseProvider):
    """
    Fetches and returns local nested stacks from a SAM Template. The SAM template passed to this provider is assumed
    to be valid, normalized and a dictionary.
    It may or may not contain a stack.
    """

    def __init__(
        self,
        template_file: str,
        stack_path: str,
        template_dict: Dict,
        parameter_overrides: Optional[Dict] = None,
        global_parameter_overrides: Optional[Dict] = None,
    ):
        """
        Initialize the class with SAM template data. The SAM template passed to this provider is assumed
        to be valid and a dictionary. This class will perform template normalization to remove structures
        like ``Globals``, resolve intrinsic functions etc.
        This class does not perform any syntactic validation of the template.
        After the class is initialized, any changes to the ``template_dict`` will not be reflected in here.
        You need to explicitly update the class with new template, if necessary.
        :param str template_file: SAM Stack Template file path
        :param str stack_path: SAM Stack stack_path (See samcli.lib.providers.provider.Stack.stack_path)
        :param dict template_dict: SAM Template as a dictionary
        :param dict parameter_overrides: Optional dictionary of values for SAM template parameters that might want
            to get substituted within the template
        :param dict global_parameter_overrides: Optional dictionary of values for SAM template global parameters that
            might want to get substituted within the template and all its child templates
        """

        self._template_file = template_file
        self._stack_path = stack_path
        self._template_dict = self.get_template(
            template_dict,
            SamLocalStackProvider.merge_parameter_overrides(parameter_overrides, global_parameter_overrides),
        )
        self._resources = self._template_dict.get("Resources", {})
        self._global_parameter_overrides = global_parameter_overrides

        LOG.debug("%d stacks found in the template", len(self._resources))

        # Store a map of stack name to stack information for quick reference -> self._stacks
        # and detect remote stacks -> self._remote_stack_full_paths
        self._stacks: Dict[str, Stack] = {}
        self.remote_stack_full_paths: List[str] = []
        self._extract_stacks()

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

    def _extract_stacks(self) -> None:
        """
        Extracts and returns nested application information from the given dictionary of SAM/CloudFormation resources.
        This method supports applications defined with AWS::Serverless::Application
        The dictionary of application LogicalId to the Application object will be assigned to self._stacks.
        If child stacks with remote URL are detected, their full paths are recorded in self._remote_stack_full_paths.
        """

        for name, resource in self._resources.items():

            resource_type = resource.get("Type")
            resource_properties = resource.get("Properties", {})
            resource_metadata = resource.get("Metadata", None)
            # Add extra metadata information to properties under a separate field.
            if resource_metadata:
                resource_properties["Metadata"] = resource_metadata

            stack: Optional[Stack] = None
            try:
                if resource_type == AWS_SERVERLESS_APPLICATION:
                    stack = SamLocalStackProvider._convert_sam_application_resource(
                        self._template_file, self._stack_path, name, resource_properties
                    )
                if resource_type == AWS_CLOUDFORMATION_STACK:
                    stack = SamLocalStackProvider._convert_cfn_stack_resource(
                        self._template_file, self._stack_path, name, resource_properties
                    )
            except RemoteStackLocationNotSupported:
                self.remote_stack_full_paths.append(get_full_path(self._stack_path, name))

            if stack:
                self._stacks[name] = stack

            # We don't care about other resource types. Just ignore them

    @staticmethod
    def _convert_sam_application_resource(
        template_file: str,
        stack_path: str,
        name: str,
        resource_properties: Dict,
        global_parameter_overrides: Optional[Dict] = None,
    ) -> Optional[Stack]:
        location = resource_properties.get("Location")

        if isinstance(location, dict):
            raise RemoteStackLocationNotSupported()

        location = cast(str, location)
        if SamLocalStackProvider.is_remote_url(location):
            raise RemoteStackLocationNotSupported()
        if location.startswith("file://"):
            location = unquote(urlparse(location).path)
        else:
            location = SamLocalStackProvider.normalize_resource_path(template_file, location)

        return Stack(
            parent_stack_path=stack_path,
            name=name,
            location=location,
            parameters=SamLocalStackProvider.merge_parameter_overrides(
                resource_properties.get("Parameters", {}), global_parameter_overrides
            ),
            template_dict=get_template_data(location),
            metadata=resource_properties.get("Metadata", {}),
        )

    @staticmethod
    def _convert_cfn_stack_resource(
        template_file: str,
        stack_path: str,
        name: str,
        resource_properties: Dict,
        global_parameter_overrides: Optional[Dict] = None,
    ) -> Optional[Stack]:
        template_url = resource_properties.get("TemplateURL")

        if isinstance(template_url, dict):
            # This happens when TemplateURL has unresolvable intrinsic functions
            # and it usually happens in CDK generated template files (#2832).
            raise RemoteStackLocationNotSupported()

        template_url = cast(str, template_url)
        if SamLocalStackProvider.is_remote_url(template_url):
            raise RemoteStackLocationNotSupported()
        if template_url.startswith("file://"):
            template_url = unquote(urlparse(template_url).path)
        else:
            template_url = SamLocalStackProvider.normalize_resource_path(template_file, template_url)

        return Stack(
            parent_stack_path=stack_path,
            name=name,
            location=template_url,
            parameters=SamLocalStackProvider.merge_parameter_overrides(
                resource_properties.get("Parameters", {}), global_parameter_overrides
            ),
            template_dict=get_template_data(template_url),
            metadata=resource_properties.get("Metadata", {}),
        )

    @staticmethod
    def get_stacks(
        template_file: str,
        stack_path: str = "",
        name: str = "",
        parameter_overrides: Optional[Dict] = None,
        global_parameter_overrides: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> Tuple[List[Stack], List[str]]:
        """
        Recursively extract stacks from a template file.

        Parameters
        ----------
        template_file: str
            the file path of the template to extract stacks from
        stack_path: str
            the stack path of the parent stack, for root stack, it is ""
        name: str
            the name of the stack associated with the template_file, for root stack, it is ""
        parameter_overrides: Optional[Dict]
            Optional dictionary of values for SAM template parameters that might want
            to get substituted within the template
        global_parameter_overrides: Optional[Dict]
            Optional dictionary of values for SAM template global parameters
            that might want to get substituted within the template and its child templates
        metadata: Optional[Dict]
            Optional dictionary of nested stack resource metadata values.

        Returns
        -------
        stacks: List[Stack]
            The list of stacks extracted from template_file
        remote_stack_full_paths : List[str]
            The list of full paths of detected remote stacks
        """
        template_dict = get_template_data(template_file)
        stacks = [
            Stack(
                stack_path,
                name,
                template_file,
                SamLocalStackProvider.merge_parameter_overrides(parameter_overrides, global_parameter_overrides),
                template_dict,
                metadata,
            )
        ]
        remote_stack_full_paths: List[str] = []

        current = SamLocalStackProvider(
            template_file, stack_path, template_dict, parameter_overrides, global_parameter_overrides
        )
        remote_stack_full_paths.extend(current.remote_stack_full_paths)

        for child_stack in current.get_all():
            stacks_in_child, remote_stack_full_paths_in_child = SamLocalStackProvider.get_stacks(
                child_stack.location,
                os.path.join(stack_path, stacks[0].stack_id),
                child_stack.name,
                child_stack.parameters,
                global_parameter_overrides,
                child_stack.metadata,
            )
            stacks.extend(stacks_in_child)
            remote_stack_full_paths.extend(remote_stack_full_paths_in_child)

        return stacks, remote_stack_full_paths

    @staticmethod
    def is_remote_url(url: str) -> bool:
        return any([url.startswith(prefix) for prefix in ["s3://", "http://", "https://"]])

    @staticmethod
    def find_root_stack(stacks: List[Stack]) -> Stack:
        candidates = [stack for stack in stacks if stack.is_root_stack]
        if not candidates:
            stacks_str = ", ".join([stack.stack_path for stack in stacks])
            raise ValueError(f"{stacks_str} does not contain a root stack")
        return candidates[0]

    @staticmethod
    def merge_parameter_overrides(
        parameter_overrides: Optional[Dict], global_parameter_overrides: Optional[Dict]
    ) -> Dict:
        """
        Combine global parameters and stack-specific parameters.
        Right now the only global parameter override available is AWS::Region (via --region in "sam local"),
        and AWS::Region won't appear in normal stack-specific parameter_overrides, so we don't
        specify which type of parameters have high precedence.

        Parameters
        ----------
        parameter_overrides: Optional[Dict]
            stack-specific parameters
        global_parameter_overrides: Optional[Dict]
            global parameters

        Returns
        -------
        Dict
            merged dict containing both global and stack-specific parameters
        """
        merged_parameter_overrides = {}
        merged_parameter_overrides.update(global_parameter_overrides or {})
        merged_parameter_overrides.update(parameter_overrides or {})
        return merged_parameter_overrides

    @staticmethod
    def normalize_resource_path(stack_file_path: str, path: str) -> str:
        """
        Convert resource paths found in nested stack to ones resolvable from root stack.
        For example,
            root stack                -> template.yaml
            child stack               -> folder/template.yaml
            a resource in child stack -> folder/resource
        the resource path is "resource" because it is extracted from child stack, the path is relative to child stack.
        here we normalize the resource path into relative paths to root stack, which is "folder/resource"

        * since stack_file_path might be a symlink, os.path.join() won't be able to derive the correct path.
          for example, stack_file_path = 'folder/t.yaml' -> '../folder2/t.yaml' and the path = 'src'
          the correct normalized path being returned should be '../folder2/t.yaml' but if we don't resolve the
          symlink first, it would return 'folder/src.'

        * symlinks on Windows might not work properly.
          https://stackoverflow.com/questions/43333640/python-os-path-realpath-for-symlink-in-windows
          For example, using Python 3.7, realpath() is a no-op (same as abspath):
            ```
            Python 3.7.8 (tags/v3.7.8:4b47a5b6ba, Jun 28 2020, 08:53:46) [MSC v.1916 64 bit (AMD64)] on win32
            Type "help", "copyright", "credits" or "license" for more information.
            >>> import os
            >>> os.symlink('some\\path', 'link1')
            >>> os.path.realpath('link1')
            'C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python37\\link1'
            >>> os.path.islink('link1')
            True
            ```
          For Python 3.8, according to manual tests, 3.8.8 can resolve symlinks correctly while 3.8.0 cannot.


        Parameters
        ----------
        stack_file_path
            The file path of the stack containing the resource
        path
            the raw path read from the template dict

        Returns
        -------
        str
            the normalized path relative to root stack

        """
        if os.path.isabs(path):
            return path

        if os.path.islink(stack_file_path):
            # os.path.realpath() always returns an absolute path while
            # the return value of this method will show up in build artifacts,
            # in case customers move the build artifacts among different machines (e.g., git or file sharing)
            # absolute paths are not robust as relative paths. So here prefer to use relative path.
            stack_file_path = os.path.relpath(os.path.realpath(stack_file_path))

        return os.path.normpath(os.path.join(os.path.dirname(stack_file_path), path))


def is_local_path(path: Union[Dict, str]) -> bool:
    return bool(path) and not isinstance(path, dict) and not SamLocalStackProvider.is_remote_url(path)


def get_local_path(path: str, parent_path: str) -> str:
    if path.startswith("file://"):
        path = unquote(urlparse(path).path)
    else:
        path = SamLocalStackProvider.normalize_resource_path(parent_path, path)
    return path
