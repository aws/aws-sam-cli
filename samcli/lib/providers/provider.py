"""
A provider class that can parse and return Lambda Functions from a variety of sources. A SAM template is one such
source
"""
import hashlib
import logging
import os
import posixpath
from collections import namedtuple
from typing import Any, Set, NamedTuple, Optional, List, Dict, Tuple, Union, cast, Iterator, TYPE_CHECKING

from samcli.commands.local.cli_common.user_exceptions import (
    InvalidLayerVersionArn,
    UnsupportedIntrinsic,
    InvalidFunctionPropertyType,
)
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.samlib.resource_metadata_normalizer import (
    ResourceMetadataNormalizer,
    SAM_METADATA_SKIP_BUILD_KEY,
    SAM_RESOURCE_ID_KEY,
)
from samcli.lib.utils.architecture import X86_64

if TYPE_CHECKING:  # pragma: no cover
    # avoid circular import, https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING
    from samcli.local.apigw.local_apigw_service import Route

LOG = logging.getLogger(__name__)


class Function(NamedTuple):
    """
    Named Tuple to representing the properties of a Lambda Function
    """

    # Function id, can be Logical ID or any function identifier to define a function in specific IaC
    function_id: str
    # Function's logical ID (used as Function name below if Property `FunctionName` is not defined)
    name: str
    # Function name (used in place of logical ID)
    functionname: str
    # Runtime/language
    runtime: Optional[str]
    # Memory in MBs
    memory: Optional[int]
    # Function Timeout in seconds
    timeout: Optional[int]
    # Name of the handler
    handler: Optional[str]
    # Image Uri
    imageuri: Optional[str]
    # Package Type
    packagetype: str
    # Image Configuration
    imageconfig: Optional[str]
    # Path to the code. This could be a S3 URI or local path or a dictionary of S3 Bucket, Key, Version
    codeuri: Optional[str]
    # Environment variables. This is a dictionary with one key called Variables inside it.
    # This contains the definition of environment variables
    environment: Optional[Dict]
    # Lambda Execution IAM Role ARN. In the future, this can be used by Local Lambda runtime to assume the IAM role
    # to get credentials to run the container with. This gives a much higher fidelity simulation of cloud Lambda.
    rolearn: Optional[str]
    # List of Layers
    layers: List["LayerVersion"]
    # Event
    events: Optional[List]
    # Metadata
    metadata: Optional[dict]
    # InlineCode
    inlinecode: Optional[str]
    # Code Signing config ARN
    codesign_config_arn: Optional[str]
    # Architecture Type
    architectures: Optional[List[str]]
    # The path of the stack relative to the root stack, it is empty for functions in root stack
    stack_path: str = ""

    @property
    def full_path(self) -> str:
        """
        Return the path-like identifier of this Function. If it is in root stack, full_path = name.
        This path is guaranteed to be unique in a multi-stack situation.
        Example:
            "HelloWorldFunction"
            "ChildStackA/GrandChildStackB/AFunctionInNestedStack"
        """
        return get_full_path(self.stack_path, self.function_id)

    @property
    def skip_build(self) -> bool:
        """
        Check if the function metadata contains SkipBuild property to determines if SAM should skip building this
        resource. It means that the customer is building the Lambda function code outside SAM, and the provided code
        path is already built.
        """
        return self.metadata.get(SAM_METADATA_SKIP_BUILD_KEY, False) if self.metadata else False

    def get_build_dir(self, build_root_dir: str) -> str:
        """
        Return the artifact directory based on the build root dir
        """
        return _get_build_dir(self, build_root_dir)

    @property
    def architecture(self) -> str:
        """
        Returns the architecture to use to build and invoke the function

        Returns
        -------
        str
            Architecture

        Raises
        ------
        InvalidFunctionPropertyType
            If the architectures value is invalid
        """
        if not self.architectures:
            return X86_64

        arch_list = cast(list, self.architectures)
        if len(arch_list) != 1:
            raise InvalidFunctionPropertyType(
                f"Function {self.name} property Architectures should be a list of length 1"
            )
        return str(arch_list[0])


class ResourcesToBuildCollector:
    def __init__(self) -> None:
        self._functions: List[Function] = []
        self._layers: List["LayerVersion"] = []

    def add_function(self, function: Function) -> None:
        self._functions.append(function)

    def add_functions(self, functions: List[Function]) -> None:
        self._functions.extend(functions)

    def add_layer(self, layer: "LayerVersion") -> None:
        self._layers.append(layer)

    def add_layers(self, layers: List["LayerVersion"]) -> None:
        self._layers.extend(layers)

    @property
    def functions(self) -> List[Function]:
        return self._functions

    @property
    def layers(self) -> List["LayerVersion"]:
        return self._layers

    def __eq__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            return self.__dict__ == other.__dict__

        return False


class LayerVersion:
    """
    Represents the LayerVersion Resource for AWS Lambda
    """

    LAYER_NAME_DELIMETER = "-"

    _name: Optional[str] = None
    _layer_id: Optional[str] = None
    _version: Optional[int] = None

    def __init__(
        self,
        arn: str,
        codeuri: Optional[str],
        compatible_runtimes: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        compatible_architectures: Optional[List[str]] = None,
        stack_path: str = "",
    ) -> None:
        """
        Parameters
        ----------
        stack_path str
            The path of the stack relative to the root stack, it is empty for layers in root stack
        name str
            Name of the layer, this can be the ARN or Logical Id in the template
        codeuri str
            CodeURI of the layer. This should contain the path to the layer code
        """
        if compatible_runtimes is None:
            compatible_runtimes = []
        if metadata is None:
            metadata = {}
        if not isinstance(arn, str):
            raise UnsupportedIntrinsic("{} is an Unsupported Intrinsic".format(arn))

        self._stack_path = stack_path
        self._arn = arn
        self._codeuri = codeuri
        self.is_defined_within_template = bool(codeuri)
        self._build_method = cast(Optional[str], metadata.get("BuildMethod", None))
        self._compatible_runtimes = compatible_runtimes

        self._build_architecture = cast(str, metadata.get("BuildArchitecture", X86_64))
        self._compatible_architectures = compatible_architectures
        self._skip_build = bool(metadata.get(SAM_METADATA_SKIP_BUILD_KEY, False))
        self._custom_layer_id = metadata.get(SAM_RESOURCE_ID_KEY)

    @staticmethod
    def _compute_layer_version(is_defined_within_template: bool, arn: str) -> Optional[int]:
        """
        Parses out the Layer version from the arn

        Parameters
        ----------
        is_defined_within_template bool
            True if the resource is a Ref to a resource otherwise False
        arn str
            ARN of the Resource

        Returns
        -------
        int
            The Version of the LayerVersion

        """

        if is_defined_within_template:
            return None

        try:
            _, layer_version = arn.rsplit(":", 1)
            return int(layer_version)
        except ValueError as ex:
            raise InvalidLayerVersionArn(arn + " is an Invalid Layer Arn.") from ex

    @staticmethod
    def _compute_layer_name(is_defined_within_template: bool, arn: str) -> str:
        """
        Computes a unique name based on the LayerVersion Arn

        Format:
        <Name of the LayerVersion>-<Version of the LayerVersion>-<sha256 of the arn>

        Parameters
        ----------
        is_defined_within_template bool
            True if the resource is a Ref to a resource otherwise False
        arn str
            ARN of the Resource

        Returns
        -------
        str
            A unique name that represents the LayerVersion
        """

        # If the Layer is defined in the template, the arn will represent the LogicalId of the LayerVersion Resource,
        # which does not require creating a name based on the arn.
        if is_defined_within_template:
            return arn

        try:
            _, layer_name, layer_version = arn.rsplit(":", 2)
        except ValueError as ex:
            raise InvalidLayerVersionArn(arn + " is an Invalid Layer Arn.") from ex

        return LayerVersion.LAYER_NAME_DELIMETER.join(
            [layer_name, layer_version, hashlib.sha256(arn.encode("utf-8")).hexdigest()[0:10]]
        )

    @property
    def stack_path(self) -> str:
        return self._stack_path

    @property
    def skip_build(self) -> bool:
        """
        Check if the function metadata contains SkipBuild property to determines if SAM should skip building this
        resource. It means that the customer is building the Lambda function code outside SAM, and the provided code
        path is already built.
        """
        return self._skip_build

    @property
    def arn(self) -> str:
        return self._arn

    @property
    def layer_id(self) -> str:
        # because self.layer_id is only used in local invoke.
        # here we delay the validation process (in _compute_layer_name) rather than in __init__() to ensure
        # customers still have a smooth build experience.
        if not self._layer_id:
            self._layer_id = cast(str, self._custom_layer_id if self._custom_layer_id else self.name)
        return self._layer_id

    @property
    def name(self) -> str:
        """
        A unique name from the arn or logical id of the Layer

        A LayerVersion Arn example:
        arn:aws:lambda:region:account-id:layer:layer-name:version

        Returns
        -------
        str
            A name of the Layer that is used on the system to uniquely identify the layer
        """
        # because self.name is only used in local invoke.
        # here we delay the validation process (in _compute_layer_name) rather than in __init__() to ensure
        # customers still have a smooth build experience.
        if not self._name:
            self._name = LayerVersion._compute_layer_name(self.is_defined_within_template, self.arn)
        return self._name

    @property
    def codeuri(self) -> Optional[str]:
        return self._codeuri

    @codeuri.setter
    def codeuri(self, codeuri: Optional[str]) -> None:
        self._codeuri = codeuri

    @property
    def version(self) -> Optional[int]:
        # because self.version is only used in local invoke.
        # here we delay the validation process (in _compute_layer_name) rather than in __init__() to ensure
        # customers still have a smooth build experience.
        if self._version is None:
            self._version = LayerVersion._compute_layer_version(self.is_defined_within_template, self.arn)
        return self._version

    @property
    def layer_arn(self) -> str:
        layer_arn, _ = self.arn.rsplit(":", 1)
        return layer_arn

    @property
    def build_method(self) -> Optional[str]:
        return self._build_method

    @property
    def compatible_runtimes(self) -> Optional[List[str]]:
        return self._compatible_runtimes

    @property
    def full_path(self) -> str:
        """
        Return the path-like identifier of this Layer. If it is in root stack, full_path = name.
        This path is guaranteed to be unique in a multi-stack situation.
        Example:
            "HelloWorldLayer"
            "ChildStackA/GrandChildStackB/ALayerInNestedStack"
        """
        return get_full_path(self.stack_path, self.layer_id)

    @property
    def build_architecture(self) -> str:
        """
        Returns
        -------
        str
            Return buildArchitecture declared in MetaData
        """
        return self._build_architecture

    @property
    def compatible_architectures(self) -> Optional[List[str]]:
        """
        Returns
        -------
        Optional[List[str]]
            Return list of compatible architecture
        """
        return self._compatible_architectures

    def get_build_dir(self, build_root_dir: str) -> str:
        """
        Return the artifact directory based on the build root dir
        """
        return _get_build_dir(self, build_root_dir)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            # self._name, self._version, and self._layer_id are generated from self._arn, and they are initialized as
            # None and their values are assigned at runtime. Here we exclude them from comparison
            overrides = {"_name": None, "_version": None, "_layer_id": None}
            return {**self.__dict__, **overrides} == {**other.__dict__, **overrides}
        return False


class Api:
    def __init__(self, routes: Optional[Union[List["Route"], Set[str]]] = None) -> None:
        if routes is None:
            routes = []
        self.routes = routes

        # Optional Dictionary containing CORS configuration on this path+method If this configuration is set,
        # then API server will automatically respond to OPTIONS HTTP method on this path and respond with appropriate
        # CORS headers based on configuration.

        self.cors: Optional[Cors] = None
        # If this configuration is set, then API server will automatically respond to OPTIONS HTTP method on this
        # path and

        self.binary_media_types_set: Set[str] = set()

        self.stage_name: Optional[str] = None
        self.stage_variables: Optional[Dict] = None

    def __hash__(self) -> int:
        # Other properties are not a part of the hash
        return hash(self.routes) * hash(self.cors) * hash(self.binary_media_types_set)

    @property
    def binary_media_types(self) -> List[str]:
        return list(self.binary_media_types_set)


_CorsTuple = namedtuple("Cors", ["allow_origin", "allow_methods", "allow_headers", "allow_credentials", "max_age"])

_CorsTuple.__new__.__defaults__ = (  # type: ignore
    None,  # Allow Origin defaults to None
    None,  # Allow Methods is optional and defaults to empty
    None,  # Allow Headers is optional and defaults to empty
    None,  # Allow Credentials is optional and defaults to empty
    None,  # MaxAge is optional and defaults to empty
)


class Cors(_CorsTuple):
    @staticmethod
    def cors_to_headers(cors: Optional["Cors"]) -> Dict[str, Union[int, str]]:
        """
        Convert CORS object to headers dictionary
        Parameters
        ----------
        cors list(samcli.commands.local.lib.provider.Cors)
            CORS configuration objcet
        Returns
        -------
            Dictionary with CORS headers
        """
        if not cors:
            return {}
        headers = {
            "Access-Control-Allow-Origin": cors.allow_origin,
            "Access-Control-Allow-Methods": cors.allow_methods,
            "Access-Control-Allow-Headers": cors.allow_headers,
            "Access-Control-Allow-Credentials": cors.allow_credentials,
            "Access-Control-Max-Age": cors.max_age,
        }
        # Filters out items in the headers dictionary that isn't empty.
        # This is required because the flask Headers dict will send an invalid 'None' string
        return {h_key: h_value for h_key, h_value in headers.items() if h_value is not None}


class AbstractApiProvider:
    """
    Abstract base class to return APIs and the functions they route to
    """

    def get_all(self) -> Iterator[Api]:
        """
        Yields all the APIs available.

        :yields Api: namedtuple containing the API information
        """
        raise NotImplementedError("not implemented")


class Stack(NamedTuple):
    """
    A class encapsulate info about a stack/sam-app resource,
    including its content, parameter overrides, file location, logicalID
    and its parent stack's stack_path (for nested stacks).
    """

    # The stack_path of the parent stack, see property stack_path for more details
    parent_stack_path: str
    # The name (logicalID) of the stack, it is empty for root stack
    name: str
    # The file location of the stack template.
    location: str
    # The parameter overrides for the stack, if there is global_parameter_overrides,
    # it is also merged into this variable.
    parameters: Optional[Dict]
    # the raw template dict
    template_dict: Dict
    # metadata
    metadata: Optional[Dict] = None

    @property
    def stack_id(self) -> str:
        _metadata = self.metadata if self.metadata else {}
        return _metadata.get(SAM_RESOURCE_ID_KEY, self.name) if self.metadata else self.name

    @property
    def stack_path(self) -> str:
        """
        The path of stack in the "nested stack tree" consisting of stack logicalIDs. It is unique.
        Example values:
            root stack: ""
            root stack's child stack StackX: "StackX"
            StackX's child stack StackY: "StackX/StackY"
        """
        return posixpath.join(self.parent_stack_path, self.stack_id)

    @property
    def is_root_stack(self) -> bool:
        """
        Return True if the stack is the root stack.
        """
        return not self.stack_path

    @property
    def resources(self) -> Dict:
        """
        Return the resources dictionary where SAM plugins have been run
        and parameter values have been substituted.
        """
        processed_template_dict: Dict = SamBaseProvider.get_template(self.template_dict, self.parameters)
        resources: Dict = processed_template_dict.get("Resources", {})
        return resources

    def get_output_template_path(self, build_root: str) -> str:
        """
        Return the path of the template yaml file output by "sam build."
        """
        # stack_path is always posix path, we need to convert it to path that matches the OS
        return os.path.join(build_root, self.stack_path.replace(posixpath.sep, os.path.sep), "template.yaml")


class ResourceIdentifier:
    """Resource identifier for representing a resource with nested stack support"""

    _stack_path: str
    # resource_iac_id is the resource logical id in case of CFN, or customer defined construct Id in case of CDK.
    _resource_iac_id: str

    def __init__(self, resource_identifier_str: str):
        """
        Parameters
        ----------
        resource_identifier_str : str
            Resource identifier in the format of:
            Stack1/Stack2/ResourceID
        """
        parts = resource_identifier_str.rsplit(posixpath.sep, 1)
        if len(parts) == 1:
            self._stack_path = ""
            # resource_iac_id in this case can be the resource iac id or logical id
            self._resource_iac_id = parts[0]
        else:
            self._stack_path = parts[0]
            # resource_iac_id in this case will be always the resource iac id
            self._resource_iac_id = parts[1]

    @property
    def stack_path(self) -> str:
        """
        Returns
        -------
        str
            Stack path of the resource.
            This can be empty string if resource is in the root stack.
        """
        return self._stack_path

    @property
    def resource_iac_id(self) -> str:
        """
        Returns
        -------
        str
            Logical ID of the resource.
        """
        return self._resource_iac_id

    def __str__(self) -> str:
        return self.stack_path + posixpath.sep + self.resource_iac_id if self.stack_path else self.resource_iac_id

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other) if isinstance(other, ResourceIdentifier) else False

    def __hash__(self) -> int:
        return hash(str(self))


def get_full_path(stack_path: str, resource_id: str) -> str:
    """
    Return the unique posix path-like identifier
    while will used for identify a resource from resources in a multi-stack situation
    """
    if not stack_path:
        return resource_id
    return posixpath.join(stack_path, resource_id)


def get_resource_by_id(
    stacks: List[Stack], identifier: ResourceIdentifier, explicit_nested: bool = False
) -> Optional[Dict[str, Any]]:
    """Seach resource in stacks based on identifier

    Parameters
    ----------
    stacks : List[Stack]
        List of stacks to be searched
    identifier : ResourceIdentifier
        Resource identifier for the resource to be returned
    explicit_nested : bool, optional
        Set to True to only search in root stack if stack_path does not exist.
        Otherwise, all stacks will be searched in order to find matching logical ID.
        If stack_path does exist in identifier, this option will be ignored and behave as if it is True

    Returns
    -------
    Dict
        Resource dict
    """
    search_all_stacks = not identifier.stack_path and not explicit_nested
    for stack in stacks:
        if stack.stack_path == identifier.stack_path or search_all_stacks:
            found_resource = None
            for logical_id, resource in stack.resources.items():
                resource_id = ResourceMetadataNormalizer.get_resource_id(resource, logical_id)
                if resource_id == identifier.resource_iac_id or (
                    not identifier.stack_path and logical_id == identifier.resource_iac_id
                ):
                    found_resource = resource
                    break

            if found_resource:
                return cast(Dict[str, Any], found_resource)
    return None


def get_resource_full_path_by_id(stacks: List[Stack], identifier: ResourceIdentifier) -> Optional[str]:
    """Seach resource in stacks based on identifier

    Parameters
    ----------
    stacks : List[Stack]
        List of stacks to be searched
    identifier : ResourceIdentifier
        Resource identifier for the resource to be returned

    Returns
    -------
    str
        return resource full path
    """
    for stack in stacks:
        if identifier.stack_path and identifier.stack_path != stack.stack_path:
            continue
        for logical_id, resource in stack.resources.items():
            resource_id = ResourceMetadataNormalizer.get_resource_id(resource, logical_id)
            if resource_id == identifier.resource_iac_id or (
                not identifier.stack_path and logical_id == identifier.resource_iac_id
            ):
                return get_full_path(stack.stack_path, resource_id)
    return None


def get_resource_ids_by_type(stacks: List[Stack], resource_type: str) -> List[ResourceIdentifier]:
    """Return list of resource IDs

    Parameters
    ----------
    stacks : List[Stack]
        List of stacks
    resource_type : str
        Resource type to be used for searching related resources.

    Returns
    -------
    List[ResourceIdentifier]
        List of ResourceIdentifiers with the type provided
    """
    resource_ids: List[ResourceIdentifier] = list()
    for stack in stacks:
        for logical_id, resource in stack.resources.items():
            resource_id = ResourceMetadataNormalizer.get_resource_id(resource, logical_id)
            if resource.get("Type", "") == resource_type:
                resource_ids.append(ResourceIdentifier(get_full_path(stack.stack_path, resource_id)))
    return resource_ids


def get_all_resource_ids(stacks: List[Stack]) -> List[ResourceIdentifier]:
    """Return all resource IDs in stacks

    Parameters
    ----------
    stacks : List[Stack]
        List of stacks

    Returns
    -------
    List[ResourceIdentifier]
        List of ResourceIdentifiers
    """
    resource_ids: List[ResourceIdentifier] = list()
    for stack in stacks:
        for logical_id, resource in stack.resources.items():
            resource_id = ResourceMetadataNormalizer.get_resource_id(resource, logical_id)
            resource_ids.append(ResourceIdentifier(get_full_path(stack.stack_path, resource_id)))
    return resource_ids


def get_unique_resource_ids(
    stacks: List[Stack],
    resource_ids: Optional[Union[List[str], Tuple[str]]],
    resource_types: Optional[Union[List[str], Tuple[str]]],
) -> Set[ResourceIdentifier]:
    """Get unique resource IDs for resource_ids and resource_types

    Parameters
    ----------
    stacks : List[Stack]
        Stacks
    resource_ids : Optional[Union[List[str], Tuple[str]]]
        Resource ID strings
    resource_types : Optional[Union[List[str], Tuple[str]]]
        Resource types

    Returns
    -------
    Set[ResourceIdentifier]
        Set of ResourceIdentifier either in resource_ids or has the type in resource_types
    """
    output_resource_ids: Set[ResourceIdentifier] = set()
    if resource_ids:
        for resources_id in resource_ids:
            output_resource_ids.add(ResourceIdentifier(resources_id))

    if resource_types:
        for resource_type in resource_types:
            resource_type_ids = get_resource_ids_by_type(stacks, resource_type)
            for resource_id in resource_type_ids:
                output_resource_ids.add(resource_id)
    return output_resource_ids


def _get_build_dir(resource: Union[Function, LayerVersion], build_root: str) -> str:
    """
    Return the build directory to place build artifact
    """
    # stack_path is always posix path, we need to convert it to path that matches the OS
    return os.path.join(build_root, resource.stack_path.replace(posixpath.sep, os.path.sep), resource.name)
