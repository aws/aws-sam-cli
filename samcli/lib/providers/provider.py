"""
A provider class that can parse and return Lambda Functions from a variety of sources. A SAM template is one such
source
"""

import hashlib
import logging
import os
import posixpath
from collections import namedtuple
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Set, Union, cast

from samcli.commands.local.cli_common.user_exceptions import (
    InvalidFunctionPropertyType,
    InvalidLayerVersionArn,
    UnsupportedIntrinsic,
)
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.samlib.resource_metadata_normalizer import (
    SAM_METADATA_SKIP_BUILD_KEY,
    SAM_RESOURCE_ID_KEY,
    ResourceMetadataNormalizer,
)
from samcli.lib.utils.architecture import X86_64
from samcli.lib.utils.packagetype import IMAGE
from samcli.lib.utils.path_utils import check_path_valid_type
from samcli.local.apigw.route import Route

LOG = logging.getLogger(__name__)

CORS_ORIGIN_HEADER = "Access-Control-Allow-Origin"
CORS_METHODS_HEADER = "Access-Control-Allow-Methods"
CORS_HEADERS_HEADER = "Access-Control-Allow-Headers"
CORS_CREDENTIALS_HEADER = "Access-Control-Allow-Credentials"
CORS_MAX_AGE_HEADER = "Access-Control-Max-Age"


class FunctionBuildInfo(Enum):
    """
    Represents information about function's build, see values for details
    """

    # buildable
    BuildableZip = "BuildableZip", "Regular ZIP function which can be build with SAM CLI"
    BuildableImage = "BuildableImage", "Regular IMAGE function which can be build with SAM CLI"
    # non-buildable
    InlineCode = "InlineCode", "A ZIP function which has inline code, non buildable"
    PreZipped = "PreZipped", "A ZIP function which points to a .zip file, non buildable"
    SkipBuild = "SkipBuild", "A Function which is denoted with SkipBuild in metadata, non buildable"
    NonBuildableImage = (
        "NonBuildableImage",
        "An IMAGE function which is missing some information to build, non buildable",
    )

    def is_buildable(self) -> bool:
        """
        Returns whether this build info can be buildable nor not
        """
        return self in {FunctionBuildInfo.BuildableZip, FunctionBuildInfo.BuildableImage}


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
    # The function url configuration
    function_url_config: Optional[Dict]
    # FunctionBuildInfo see implementation doc for its details
    function_build_info: FunctionBuildInfo
    # The path of the stack relative to the root stack, it is empty for functions in root stack
    stack_path: str = ""
    # Configuration for runtime management. Includes the fields `UpdateRuntimeOn` and `RuntimeVersionArn` (optional).
    runtime_management_config: Optional[Dict] = None
    # LoggingConfig for Advanced logging
    logging_config: Optional[Dict] = None

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
        return get_skip_build(self.metadata)

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
        self._metadata = metadata
        self._build_method = cast(Optional[str], metadata.get("BuildMethod", None))
        self._compatible_runtimes = compatible_runtimes
        self._custom_layer_id = metadata.get(SAM_RESOURCE_ID_KEY)

        self._build_architecture = cast(str, metadata.get("BuildArchitecture", X86_64))
        self._compatible_architectures = compatible_architectures

        self._skip_build = bool(metadata.get(SAM_METADATA_SKIP_BUILD_KEY, False))

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
    def metadata(self) -> Dict:
        return self._metadata

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


_CorsTuple = namedtuple(
    "_CorsTuple", ["allow_origin", "allow_methods", "allow_headers", "allow_credentials", "max_age"]
)

_CorsTuple.__new__.__defaults__ = (
    None,  # Allow Origin defaults to None
    None,  # Allow Methods is optional and defaults to empty
    None,  # Allow Headers is optional and defaults to empty
    None,  # Allow Credentials is optional and defaults to empty
    None,  # MaxAge is optional and defaults to empty
)


class Cors(_CorsTuple):
    @staticmethod
    def cors_to_headers(
        cors: Optional["Cors"], request_origin: Optional[str], event_type: str
    ) -> Dict[str, Union[int, str]]:
        """
        Convert CORS object to headers dictionary
        Parameters
        ----------
        cors list(samcli.commands.local.lib.provider.Cors)
            CORS configuration objcet
        request_origin str
            Origin of the request, e.g. https://example.com:8080
        event_type str
            The type of the APIGateway resource that contain the route, either Api, or HttpApi
        Returns
        -------
            Dictionary with CORS headers
        """
        if not cors:
            return {}

        if event_type == Route.API:
            # the CORS behaviour in Rest API gateway is to return whatever defined in the ResponseParameters of
            # the method integration resource
            headers = {
                CORS_ORIGIN_HEADER: cors.allow_origin,
                CORS_METHODS_HEADER: cors.allow_methods,
                CORS_HEADERS_HEADER: cors.allow_headers,
                CORS_CREDENTIALS_HEADER: cors.allow_credentials,
                CORS_MAX_AGE_HEADER: cors.max_age,
            }
        else:
            # Resource processing start here.
            # The following code is based on the following spec:
            # https://www.w3.org/TR/2020/SPSD-cors-20200602/#resource-processing-model

            if not request_origin:
                return {}

            # cors.allow_origin can be either a single origin or comma separated list of origins
            allowed_origins = cors.allow_origin.split(",") if cors.allow_origin else list()
            allowed_origins = [origin.strip() for origin in allowed_origins]

            matched_origin = None
            if "*" in allowed_origins:
                matched_origin = "*"
            elif request_origin in allowed_origins:
                matched_origin = request_origin

            if matched_origin is None:
                return {}

            headers = {
                CORS_ORIGIN_HEADER: matched_origin,
                CORS_METHODS_HEADER: cors.allow_methods,
                CORS_HEADERS_HEADER: cors.allow_headers,
                CORS_CREDENTIALS_HEADER: cors.allow_credentials,
                CORS_MAX_AGE_HEADER: cors.max_age,
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


class Stack:
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

    def __init__(
        self,
        parent_stack_path: str,
        name: str,
        location: str,
        parameters: Optional[Dict],
        template_dict: Dict,
        metadata: Optional[Dict[str, str]] = None,
    ):
        self.parent_stack_path = parent_stack_path
        self.name = name
        self.location = location
        self.parameters = parameters
        self.template_dict = template_dict
        self.metadata = metadata
        self._resources: Optional[Dict] = None
        self._raw_resources: Optional[Dict] = None

    @property
    def stack_id(self) -> str:
        _metadata: Dict[str, str] = self.metadata or {}
        return _metadata.get(SAM_RESOURCE_ID_KEY, self.name)

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
        if self._resources is not None:
            return self._resources
        processed_template_dict: Dict[str, Dict] = SamBaseProvider.get_template(self.template_dict, self.parameters)
        self._resources = processed_template_dict.get("Resources", {})
        return self._resources

    @property
    def raw_resources(self) -> Dict:
        """
        Return the resources dictionary without running SAM Transform
        """
        if self._raw_resources is not None:
            return self._raw_resources
        self._raw_resources = cast(Dict, self.template_dict.get("Resources", {}))
        return self._raw_resources

    def get_output_template_path(self, build_root: str) -> str:
        """
        Return the path of the template yaml file output by "sam build."
        """
        # stack_path is always posix path, we need to convert it to path that matches the OS
        return os.path.join(build_root, self.stack_path.replace(posixpath.sep, os.path.sep), "template.yaml")

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Stack):
            return (
                self.is_root_stack == other.is_root_stack
                and self.location == other.location
                and self.metadata == other.metadata
                and self.name == other.name
                and self.parameters == other.parameters
                and self.parent_stack_path == other.parent_stack_path
                and self.stack_id == other.stack_id
                and self.stack_path == other.stack_path
                and self.template_dict == other.template_dict
            )
        return False

    @staticmethod
    def get_parent_stack(child_stack: "Stack", stacks: List["Stack"]) -> Optional["Stack"]:
        """
        Return parent stack for the given child stack
        Parameters
        ----------
        child_stack Stack
            the child stack
        stacks : List[Stack]
            a list of stack for searching
        Returns
        -------
        Stack
            parent stack of the given child stack, if the child stack is root, return None
        """
        if child_stack.is_root_stack:
            return None

        parent_stack_path = child_stack.parent_stack_path
        for stack in stacks:
            if stack.stack_path == parent_stack_path:
                return stack
        return None

    @staticmethod
    def get_stack_by_full_path(full_path: str, stacks: List["Stack"]) -> Optional["Stack"]:
        """
        Return the stack with given full path
        Parameters
        ----------
        full_path str
            full path of the stack like ChildStack/ChildChildStack
        stacks : List[Stack]
            a list of stack for searching
        Returns
        -------
        Stack
            The stack with the given full path
        """
        for stack in stacks:
            if stack.stack_path == full_path:
                return stack
        return None

    @staticmethod
    def get_child_stacks(stack: "Stack", stacks: List["Stack"]) -> List["Stack"]:
        """
        Return child stacks for the given parent stack
        Parameters
        ----------
        stack Stack
            the parent stack
        stacks : List[Stack]
            a list of stack for searching
        Returns
        -------
        List[Stack]
            child stacks of the given parent stack
        """
        child_stacks = []
        for child in stacks:
            if not child.is_root_stack and child.parent_stack_path == stack.stack_path:
                child_stacks.append(child)
        return child_stacks


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
    resource_ids: Optional[Union[List[str]]],
    resource_types: Optional[Union[List[str]]],
) -> Set[ResourceIdentifier]:
    """Get unique resource IDs for resource_ids and resource_types

    Parameters
    ----------
    stacks : List[Stack]
        Stacks
    resource_ids : Optional[Union[List[str]]]
        Resource ID strings
    resource_types : Optional[Union[List[str]]]
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


def get_skip_build(metadata: Optional[Dict[str, bool]]) -> bool:
    """
    Returns the value of SkipBuild property from Metadata, False if it is not defined
    """
    return metadata.get(SAM_METADATA_SKIP_BUILD_KEY, False) if metadata else False


def get_function_build_info(
    full_path: str,
    packagetype: str,
    inlinecode: Optional[str],
    codeuri: Optional[str],
    imageuri: Optional[str],
    metadata: Optional[Dict],
) -> FunctionBuildInfo:
    """
    Populates FunctionBuildInfo from the given information.
    """
    if inlinecode:
        LOG.debug("Skip building inline function: %s", full_path)
        return FunctionBuildInfo.InlineCode

    if isinstance(codeuri, str) and codeuri.endswith(".zip"):
        LOG.debug("Skip building zip function: %s", full_path)
        return FunctionBuildInfo.PreZipped

    if get_skip_build(metadata):
        LOG.debug("Skip building pre-built function: %s", full_path)
        return FunctionBuildInfo.SkipBuild

    if packagetype == IMAGE:
        metadata = metadata or {}
        dockerfile = cast(str, metadata.get("Dockerfile", ""))
        docker_context = cast(str, metadata.get("DockerContext", ""))
        buildable = dockerfile and docker_context
        loadable = imageuri and check_path_valid_type(imageuri) and Path(imageuri).is_file()
        if not buildable and not loadable:
            LOG.debug(
                "Skip Building %s function, as it is missing either Dockerfile or DockerContext "
                "metadata properties.",
                full_path,
            )
            return FunctionBuildInfo.NonBuildableImage
        return FunctionBuildInfo.BuildableImage

    return FunctionBuildInfo.BuildableZip


def _get_build_dir(resource: Union[Function, LayerVersion], build_root: str) -> str:
    """
    Return the build directory to place build artifact
    """
    # stack_path is always posix path, we need to convert it to path that matches the OS
    return os.path.join(build_root, resource.stack_path.replace(posixpath.sep, os.path.sep), resource.name)
