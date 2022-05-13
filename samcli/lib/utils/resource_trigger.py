"""ResourceTrigger Classes for Creating PathHandlers According to a Resource"""
import re
import platform

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from typing_extensions import Protocol
from watchdog.events import FileSystemEvent, RegexMatchingEventHandler

from samcli.lib.providers.exceptions import MissingCodeUri, MissingLocalDefinition, InvalidTemplateFile
from samcli.lib.providers.provider import Function, LayerVersion, ResourceIdentifier, Stack, get_resource_by_id
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_layer_provider import SamLayerProvider
from samcli.lib.utils.definition_validator import DefinitionValidator
from samcli.lib.utils.path_observer import PathHandler
from samcli.local.lambdafn.exceptions import FunctionNotFound, ResourceNotFound
from samcli.lib.utils.resources import RESOURCES_WITH_LOCAL_PATHS


AWS_SAM_FOLDER_REGEX = "^.*\\.aws-sam.*$"


class OnChangeCallback(Protocol):
    """Callback Type"""

    def __call__(self, event: Optional[FileSystemEvent] = None) -> None:
        pass


class ResourceTrigger(ABC):
    """Abstract class for creating PathHandlers for a resource.
    PathHandlers returned by get_path_handlers() can then be used with an observer for
    detecting file changes associated with the resource."""

    def __init__(self) -> None:
        pass

    @abstractmethod
    def get_path_handlers(self) -> List[PathHandler]:
        """List of PathHandlers that corresponds to a resource
        Returns
        -------
        List[PathHandler]
            List of PathHandlers that corresponds to a resource
        """
        raise NotImplementedError("get_path_handleres is not implemented.")

    @staticmethod
    def get_single_file_path_handler(file_path: Path) -> PathHandler:
        """Get PathHandler for watching a single file

        Parameters
        ----------
        file_path : Path
            File path object

        Returns
        -------
        PathHandler
            The PathHandler for the file specified
        """
        file_path = file_path.resolve()
        folder_path = file_path.parent
        case_sensitive = platform.system().lower() != "windows"
        file_handler = RegexMatchingEventHandler(
            regexes=[f"^{re.escape(str(file_path))}$"],
            ignore_regexes=[],
            ignore_directories=True,
            case_sensitive=case_sensitive,
        )
        return PathHandler(path=folder_path, event_handler=file_handler, recursive=False)

    @staticmethod
    def get_dir_path_handler(dir_path: Path, ignore_regexes: Optional[List[str]] = None) -> PathHandler:
        """Get PathHandler for watching a single directory

        Parameters
        ----------
        dir_path : Path
            Folder path object
        ignore_regexes : List[str], Optional
            List of regexes that should be ignored

        Returns
        -------
        PathHandler
            The PathHandler for the folder specified
        """
        dir_path = dir_path.resolve()

        case_sensitive = platform.system().lower() != "windows"

        file_handler = RegexMatchingEventHandler(
            regexes=["^.*$"],
            ignore_regexes=ignore_regexes,
            ignore_directories=False,
            case_sensitive=case_sensitive,
        )
        return PathHandler(path=dir_path, event_handler=file_handler, recursive=True, static_folder=True)


class TemplateTrigger(ResourceTrigger):
    _template_file: str
    _stack_name: str
    _on_template_change: OnChangeCallback
    _validator: DefinitionValidator

    def __init__(self, template_file: str, stack_name: str, on_template_change: OnChangeCallback) -> None:
        """
        Parameters
        ----------
        template_file : str
            Template file to be watched
        stack_name: str
            Stack name of the template
        on_template_change : OnChangeCallback
            Callback when template changes
        """
        super().__init__()
        self._template_file = template_file
        self._stack_name = stack_name
        self._on_template_change = on_template_change
        self._validator = DefinitionValidator(Path(self._template_file))

    def validate_template(self):
        if not self._validator.validate_file():
            raise InvalidTemplateFile(self._template_file, self._stack_name)

    def _validator_wrapper(self, event: Optional[FileSystemEvent] = None) -> None:
        """Wrapper for callback that only executes if the template is valid and non-trivial changes are detected.

        Parameters
        ----------
        event : Optional[FileSystemEvent], optional
        """
        if self._validator.validate_change():
            self._on_template_change(event)

    def get_path_handlers(self) -> List[PathHandler]:
        file_path_handler = ResourceTrigger.get_single_file_path_handler(Path(self._template_file))
        file_path_handler.event_handler.on_any_event = self._validator_wrapper
        return [file_path_handler]


class CodeResourceTrigger(ResourceTrigger):
    """Parent class for ResourceTriggers that are for a single template resource."""

    _resource_identifier: ResourceIdentifier
    _resource: Dict[str, Any]
    _on_code_change: OnChangeCallback

    def __init__(
        self,
        resource_identifier: ResourceIdentifier,
        stacks: List[Stack],
        base_dir: Path,
        on_code_change: OnChangeCallback,
    ):
        """
        Parameters
        ----------
        resource_identifier : ResourceIdentifier
            ResourceIdentifier
        stacks : List[Stack]
            List of stacks
        base_dir: Path
            Base directory for the resource. This should be the path to template file in most cases.
        on_code_change : OnChangeCallback
            Callback when the resource files are changed.

        Raises
        ------
        ResourceNotFound
            Raised when the resource cannot be found in the stacks.
        """
        super().__init__()
        self._resource_identifier = resource_identifier
        resource = get_resource_by_id(stacks, resource_identifier)
        if not resource:
            raise ResourceNotFound()
        self._resource = resource
        self._on_code_change = on_code_change
        self.base_dir = base_dir


class LambdaFunctionCodeTrigger(CodeResourceTrigger):
    _function: Function
    _code_uri: str

    def __init__(
        self,
        function_identifier: ResourceIdentifier,
        stacks: List[Stack],
        base_dir: Path,
        on_code_change: OnChangeCallback,
    ):
        """
        Parameters
        ----------
        function_identifier : ResourceIdentifier
            ResourceIdentifier for the function
        stacks : List[Stack]
            List of stacks
        base_dir: Path
            Base directory for the function. This should be the path to template file in most cases.
        on_code_change : OnChangeCallback
            Callback when function code files are changed.

        Raises
        ------
        FunctionNotFound
            raised when the function cannot be found in stacks
        MissingCodeUri
            raised when there is no CodeUri property in the function definition.
        """
        super().__init__(function_identifier, stacks, base_dir, on_code_change)
        function = SamFunctionProvider(stacks).get(str(function_identifier))
        if not function:
            raise FunctionNotFound()
        self._function = function

        code_uri = self._get_code_uri()
        if not code_uri:
            raise MissingCodeUri()
        self._code_uri = code_uri

    @abstractmethod
    def _get_code_uri(self) -> Optional[str]:
        """
        Returns
        -------
        Optional[str]
            Path for the folder to be watched.
        """
        raise NotImplementedError()

    def get_path_handlers(self) -> List[PathHandler]:
        """
        Returns
        -------
        List[PathHandler]
            PathHandlers for the code folder associated with the function
        """
        dir_path_handler = ResourceTrigger.get_dir_path_handler(
            self.base_dir.joinpath(self._code_uri), ignore_regexes=[AWS_SAM_FOLDER_REGEX]
        )
        dir_path_handler.self_create = self._on_code_change
        dir_path_handler.self_delete = self._on_code_change
        dir_path_handler.event_handler.on_any_event = self._on_code_change
        return [dir_path_handler]


class LambdaZipCodeTrigger(LambdaFunctionCodeTrigger):
    def _get_code_uri(self) -> Optional[str]:
        return self._function.codeuri


class LambdaImageCodeTrigger(LambdaFunctionCodeTrigger):
    def _get_code_uri(self) -> Optional[str]:
        if not self._function.metadata:
            return None
        return cast(Optional[str], self._function.metadata.get("DockerContext", None))


class LambdaLayerCodeTrigger(CodeResourceTrigger):
    _layer: LayerVersion
    _code_uri: str

    def __init__(
        self,
        layer_identifier: ResourceIdentifier,
        stacks: List[Stack],
        base_dir: Path,
        on_code_change: OnChangeCallback,
    ):
        """
        Parameters
        ----------
        layer_identifier : ResourceIdentifier
            ResourceIdentifier for the layer
        stacks : List[Stack]
            List of stacks
        base_dir: Path
            Base directory for the layer. This should be the path to template file in most cases.
        on_code_change : OnChangeCallback
            Callback when layer code files are changed.

        Raises
        ------
        ResourceNotFound
            raised when the layer cannot be found in stacks
        MissingCodeUri
            raised when there is no CodeUri property in the function definition.
        """
        super().__init__(layer_identifier, stacks, base_dir, on_code_change)
        layer = SamLayerProvider(stacks).get(str(layer_identifier))
        if not layer:
            raise ResourceNotFound()
        self._layer = layer
        code_uri = self._layer.codeuri
        if not code_uri:
            raise MissingCodeUri()
        self._code_uri = code_uri

    def get_path_handlers(self) -> List[PathHandler]:
        """
        Returns
        -------
        List[PathHandler]
            PathHandlers for the code folder associated with the layer
        """
        dir_path_handler = ResourceTrigger.get_dir_path_handler(
            self.base_dir.joinpath(self._code_uri), ignore_regexes=[AWS_SAM_FOLDER_REGEX]
        )
        dir_path_handler.self_create = self._on_code_change
        dir_path_handler.self_delete = self._on_code_change
        dir_path_handler.event_handler.on_any_event = self._on_code_change
        return [dir_path_handler]


class DefinitionCodeTrigger(CodeResourceTrigger):
    _validator: DefinitionValidator
    _definition_file: str

    def __init__(
        self,
        resource_identifier: ResourceIdentifier,
        resource_type: str,
        stacks: List[Stack],
        base_dir: Path,
        on_code_change: OnChangeCallback,
    ):
        """
        Parameters
        ----------
        resource_identifier : ResourceIdentifier
            ResourceIdentifier for the Resource
        resource_type : str
            Resource type
        stacks : List[Stack]
            List of stacks
        base_dir: Path
            Base directory for the definition file. This should be the path to template file in most cases.
        on_code_change : OnChangeCallback
            Callback when definition file is changed.
        """
        super().__init__(resource_identifier, stacks, base_dir, on_code_change)
        self._resource_type = resource_type
        self._definition_file = self._get_definition_file()
        self._validator = DefinitionValidator(self.base_dir.joinpath(self._definition_file))

    def _get_definition_file(self) -> str:
        """
        Returns
        -------
        str
            JSON/YAML definition file path

        Raises
        ------
        MissingLocalDefinition
            raised when resource property related to definition path is not specified.
        """
        property_name = RESOURCES_WITH_LOCAL_PATHS[self._resource_type][0]
        definition_file = self._resource.get("Properties", {}).get(property_name)
        if not definition_file or not isinstance(definition_file, str):
            raise MissingLocalDefinition(self._resource_identifier, property_name)
        return definition_file

    def _validator_wrapper(self, event: Optional[FileSystemEvent] = None):
        """Wrapper for callback that only executes if the definition is valid and non-trivial changes are detected.

        Parameters
        ----------
        event : Optional[FileSystemEvent], optional
        """
        if self._validator.validate_change():
            self._on_code_change(event)

    def get_path_handlers(self) -> List[PathHandler]:
        """
        Returns
        -------
        List[PathHandler]
            A single PathHandler for watching the definition file.
        """
        file_path_handler = ResourceTrigger.get_single_file_path_handler(self.base_dir.joinpath(self._definition_file))
        file_path_handler.event_handler.on_any_event = self._validator_wrapper
        return [file_path_handler]
