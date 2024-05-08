"""
Holds classes and utility methods related to build graph
"""

import copy
import logging
import os
import threading
from abc import abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple, cast
from uuid import uuid4

import tomlkit
from tomlkit.toml_document import TOMLDocument

from samcli.commands._utils.experimental import ExperimentalFlag, is_experimental_enabled
from samcli.lib.build.exceptions import InvalidBuildGraphException
from samcli.lib.providers.provider import Function, LayerVersion
from samcli.lib.samlib.resource_metadata_normalizer import (
    SAM_IS_NORMALIZED,
    SAM_RESOURCE_ID_KEY,
)
from samcli.lib.utils.architecture import X86_64
from samcli.lib.utils.packagetype import ZIP

LOG = logging.getLogger(__name__)

DEFAULT_BUILD_GRAPH_FILE_NAME = "build.toml"

DEFAULT_DEPENDENCIES_DIR = os.path.join(".aws-sam", "deps")

# filed names for the toml table
PACKAGETYPE_FIELD = "packagetype"
CODE_URI_FIELD = "codeuri"
RUNTIME_FIELD = "runtime"
METADATA_FIELD = "metadata"
FUNCTIONS_FIELD = "functions"
SOURCE_HASH_FIELD = "source_hash"
MANIFEST_HASH_FIELD = "manifest_hash"
ENV_VARS_FIELD = "env_vars"
LAYER_NAME_FIELD = "layer_name"
BUILD_METHOD_FIELD = "build_method"
COMPATIBLE_RUNTIMES_FIELD = "compatible_runtimes"
LAYER_FIELD = "layer"
ARCHITECTURE_FIELD = "architecture"
HANDLER_FIELD = "handler"
SHARED_CODEURI_SUFFIX = "Shared"

# Compiled runtimes that we need to compare handlers for
COMPILED_RUNTIMES = ["go1.x"]


def _function_build_definition_to_toml_table(
    function_build_definition: "FunctionBuildDefinition",
) -> tomlkit.api.Table:
    """
    Converts given function_build_definition into toml table representation

    Parameters
    ----------
    function_build_definition: FunctionBuildDefinition
        FunctionBuildDefinition which will be converted into toml table

    Returns
    -------
    tomlkit.api.Table
        toml table of FunctionBuildDefinition
    """
    toml_table = tomlkit.table()
    if function_build_definition.packagetype == ZIP:
        toml_table[CODE_URI_FIELD] = function_build_definition.codeuri
        toml_table[RUNTIME_FIELD] = function_build_definition.runtime
        toml_table[ARCHITECTURE_FIELD] = function_build_definition.architecture
        toml_table[HANDLER_FIELD] = function_build_definition.handler
        if function_build_definition.source_hash:
            toml_table[SOURCE_HASH_FIELD] = function_build_definition.source_hash
        toml_table[MANIFEST_HASH_FIELD] = function_build_definition.manifest_hash
    toml_table[PACKAGETYPE_FIELD] = function_build_definition.packagetype
    toml_table[FUNCTIONS_FIELD] = [f.full_path for f in function_build_definition.functions]

    if function_build_definition.metadata:
        toml_table[METADATA_FIELD] = function_build_definition.metadata
    if function_build_definition.env_vars:
        toml_table[ENV_VARS_FIELD] = function_build_definition.env_vars

    return toml_table


def _toml_table_to_function_build_definition(uuid: str, toml_table: tomlkit.api.Table) -> "FunctionBuildDefinition":
    """
    Converts given toml table into FunctionBuildDefinition instance

    Parameters
    ----------
    uuid: str
        key of the function toml_table instance
    toml_table: tomlkit.api.Table
        function build definition as toml table

    Returns
    -------
    FunctionBuildDefinition
        FunctionBuildDefinition of given toml table
    """
    function_build_definition = FunctionBuildDefinition(
        toml_table.get(RUNTIME_FIELD),
        toml_table.get(CODE_URI_FIELD),
        None,
        toml_table.get(PACKAGETYPE_FIELD, ZIP),
        toml_table.get(ARCHITECTURE_FIELD, X86_64),
        dict(toml_table.get(METADATA_FIELD, {})),
        toml_table.get(HANDLER_FIELD, ""),
        toml_table.get(SOURCE_HASH_FIELD, ""),
        toml_table.get(MANIFEST_HASH_FIELD, ""),
        dict(toml_table.get(ENV_VARS_FIELD, {})),
    )
    function_build_definition.uuid = uuid
    return function_build_definition


def _layer_build_definition_to_toml_table(layer_build_definition: "LayerBuildDefinition") -> tomlkit.api.Table:
    """
    Converts given layer_build_definition into toml table representation

    Parameters
    ----------
    layer_build_definition: LayerBuildDefinition
        LayerBuildDefinition which will be converted into toml table

    Returns
    -------
    tomlkit.api.Table
        toml table of LayerBuildDefinition
    """
    toml_table = tomlkit.table()
    toml_table[LAYER_NAME_FIELD] = layer_build_definition.full_path
    toml_table[CODE_URI_FIELD] = layer_build_definition.codeuri
    toml_table[BUILD_METHOD_FIELD] = layer_build_definition.build_method
    toml_table[COMPATIBLE_RUNTIMES_FIELD] = layer_build_definition.compatible_runtimes
    toml_table[ARCHITECTURE_FIELD] = layer_build_definition.architecture
    if layer_build_definition.source_hash:
        toml_table[SOURCE_HASH_FIELD] = layer_build_definition.source_hash
    toml_table[MANIFEST_HASH_FIELD] = layer_build_definition.manifest_hash
    if layer_build_definition.env_vars:
        toml_table[ENV_VARS_FIELD] = layer_build_definition.env_vars
    toml_table[LAYER_FIELD] = layer_build_definition.layer.full_path

    return toml_table


def _toml_table_to_layer_build_definition(uuid: str, toml_table: tomlkit.api.Table) -> "LayerBuildDefinition":
    """
    Converts given toml table into LayerBuildDefinition instance

    Parameters
    ----------
    uuid: str
        key of the toml_table instance
    toml_table:  tomlkit.api.Table
        layer build definition as toml table

    Returns
    -------
    LayerBuildDefinition
        LayerBuildDefinition of given toml table
    """
    layer_build_definition = LayerBuildDefinition(
        toml_table.get(LAYER_NAME_FIELD, ""),
        toml_table.get(CODE_URI_FIELD),
        toml_table.get(BUILD_METHOD_FIELD),
        toml_table.get(COMPATIBLE_RUNTIMES_FIELD),
        toml_table.get(ARCHITECTURE_FIELD, X86_64),
        toml_table.get(SOURCE_HASH_FIELD, ""),
        toml_table.get(MANIFEST_HASH_FIELD, ""),
        dict(toml_table.get(ENV_VARS_FIELD, {})),
    )
    layer_build_definition.uuid = uuid
    return layer_build_definition


class BuildHashingInformation(NamedTuple):
    """
    Holds hashing information for the source folder and the manifest file
    """

    source_hash: str
    manifest_hash: str


class BuildGraph:
    """
    Contains list of build definitions, with ability to read and write them into build.toml file
    """

    # private lock for build.toml reads and writes
    __toml_lock = threading.Lock()

    # global table build definitions key
    FUNCTION_BUILD_DEFINITIONS = "function_build_definitions"
    LAYER_BUILD_DEFINITIONS = "layer_build_definitions"

    def __init__(self, build_dir: str) -> None:
        # put build.toml file inside .aws-sam folder
        self._filepath = Path(build_dir).parent.joinpath(DEFAULT_BUILD_GRAPH_FILE_NAME)
        self._function_build_definitions: List["FunctionBuildDefinition"] = []
        self._layer_build_definitions: List["LayerBuildDefinition"] = []
        self._atomic_read()

    def get_function_build_definitions(self) -> Tuple["FunctionBuildDefinition", ...]:
        return tuple(self._function_build_definitions)

    def get_layer_build_definitions(self) -> Tuple["LayerBuildDefinition", ...]:
        return tuple(self._layer_build_definitions)

    def get_function_build_definition_with_full_path(
        self, function_full_path: str
    ) -> Optional["FunctionBuildDefinition"]:
        """
        Returns FunctionBuildDefinition instance of given function logical id.

        Parameters
        ----------
        function_full_path : str
            Function full path that will be searched in the function build definitions

        Returns
        -------
        Optional[FunctionBuildDefinition]
            If a function build definition found returns it, otherwise returns None

        """
        for function_build_definition in self._function_build_definitions:
            for build_definition_function in function_build_definition.functions:
                if build_definition_function.full_path == function_full_path:
                    return function_build_definition
        return None

    def put_function_build_definition(
        self, function_build_definition: "FunctionBuildDefinition", function: Function
    ) -> None:
        """
        Puts the newly read function build definition into existing build graph.
        If graph already contains a function build definition which is same as the newly passed one, then it will add
        the function to the existing one, discarding the new one

        If graph doesn't contain such unique function build definition, it will be added to the current build graph

        Parameters
        ----------
        function_build_definition: FunctionBuildDefinition
            function build definition which is newly read from template.yaml file
        function: Function
            function details for this function build definition
        """
        if function_build_definition in self._function_build_definitions:
            previous_build_definition = self._function_build_definitions[
                self._function_build_definitions.index(function_build_definition)
            ]
            LOG.debug(
                "Same function build definition found, adding function (Previous: %s, Current: %s, Function: %s)",
                previous_build_definition,
                function_build_definition,
                function,
            )
            previous_build_definition.add_function(function)
        else:
            LOG.debug(
                "Unique function build definition found, adding as new (Function Build Definition: %s, Function: %s)",
                function_build_definition,
                function,
            )
            function_build_definition.add_function(function)
            self._function_build_definitions.append(function_build_definition)

    def put_layer_build_definition(self, layer_build_definition: "LayerBuildDefinition", layer: LayerVersion) -> None:
        """
        Puts the newly read layer build definition into existing build graph.
        If graph already contains a layer build definition which is same as the newly passed one, then it will add
        the layer to the existing one, discarding the new one

        If graph doesn't contain such unique layer build definition, it will be added to the current build graph

        Parameters
        ----------
        layer_build_definition: LayerBuildDefinition
            layer build definition which is newly read from template.yaml file
        layer: Layer
            layer details for this layer build definition
        """
        if layer_build_definition in self._layer_build_definitions:
            previous_build_definition = self._layer_build_definitions[
                self._layer_build_definitions.index(layer_build_definition)
            ]
            LOG.debug(
                "Same Layer build definition found, adding layer (Previous: %s, Current: %s, Layer: %s)",
                previous_build_definition,
                layer_build_definition,
                layer,
            )
            previous_build_definition.layer = layer
        else:
            LOG.debug(
                "Unique Layer build definition found, adding as new (Layer Build Definition: %s, Layer: %s)",
                layer_build_definition,
                layer,
            )
            layer_build_definition.layer = layer
            self._layer_build_definitions.append(layer_build_definition)

    def clean_redundant_definitions_and_update(self, persist: bool) -> None:
        """
        Removes build definitions which doesn't have any function in it, which means these build definitions
        are no longer used, and they can be deleted

        If persist parameter is given True, build graph is written to .aws-sam/build.toml file
        """
        self._function_build_definitions[:] = [
            fbd for fbd in self._function_build_definitions if len(fbd.functions) > 0
        ]
        self._layer_build_definitions[:] = [bd for bd in self._layer_build_definitions if bd.layer]
        if persist:
            self._atomic_write()

    def update_definition_hash(self) -> None:
        """
        Updates the build.toml file with the newest source_hash values of the partial build's definitions

        This operation is atomic, that no other thread accesses build.toml
        during the process of reading and modifying the hash value
        """
        with BuildGraph.__toml_lock:
            stored_function_definitions = copy.deepcopy(self._function_build_definitions)
            stored_layer_definitions = copy.deepcopy(self._layer_build_definitions)
            self._read()

            function_content = BuildGraph._compare_hash_changes(
                stored_function_definitions, self._function_build_definitions
            )
            layer_content = BuildGraph._compare_hash_changes(stored_layer_definitions, self._layer_build_definitions)

            if function_content or layer_content:
                self._write_source_hash(function_content, layer_content)

            self._function_build_definitions = stored_function_definitions
            self._layer_build_definitions = stored_layer_definitions

    @staticmethod
    def _compare_hash_changes(
        input_list: Sequence["AbstractBuildDefinition"], compared_list: Sequence["AbstractBuildDefinition"]
    ) -> Dict[str, BuildHashingInformation]:
        """
        Helper to compare the function and layer definition changes in hash value

        Returns a dictionary that has uuid as key, updated hash value as value
        """
        content = {}
        for compared_def in compared_list:
            for stored_def in input_list:
                if stored_def == compared_def:
                    old_hash = compared_def.source_hash
                    updated_hash = stored_def.source_hash
                    old_manifest_hash = compared_def.manifest_hash
                    updated_manifest_hash = stored_def.manifest_hash
                    uuid = stored_def.uuid
                    if old_hash != updated_hash or old_manifest_hash != updated_manifest_hash:
                        content[uuid] = BuildHashingInformation(updated_hash, updated_manifest_hash)
                    compared_def.download_dependencies = old_manifest_hash != updated_manifest_hash
        return content

    def _write_source_hash(
        self, function_content: Dict[str, BuildHashingInformation], layer_content: Dict[str, BuildHashingInformation]
    ) -> None:
        """
        Helper to write source_hash values to build.toml file
        """
        if not self._filepath.exists():
            open(self._filepath, "a+").close()  # pylint: disable=consider-using-with

        txt = self._filepath.read_text()
        # .loads() returns a TOMLDocument,
        # and it behaves like a standard dictionary according to https://github.com/sdispater/tomlkit.
        # in tomlkit 0.7.2, the types are broken (tomlkit#128, #130, #134) so here we convert it to Dict.
        document = cast(Dict[str, Dict[str, Any]], tomlkit.loads(txt))

        for function_uuid, hashing_info in function_content.items():
            if function_uuid in document.get(BuildGraph.FUNCTION_BUILD_DEFINITIONS, {}):
                function_build_definition = document[BuildGraph.FUNCTION_BUILD_DEFINITIONS][function_uuid]
                function_build_definition[SOURCE_HASH_FIELD] = hashing_info.source_hash
                function_build_definition[MANIFEST_HASH_FIELD] = hashing_info.manifest_hash
                LOG.info(
                    "Updated source_hash and manifest_hash field in build.toml for function with UUID %s", function_uuid
                )

        for layer_uuid, hashing_info in layer_content.items():
            if layer_uuid in document.get(BuildGraph.LAYER_BUILD_DEFINITIONS, {}):
                layer_build_definition = document[BuildGraph.LAYER_BUILD_DEFINITIONS][layer_uuid]
                layer_build_definition[SOURCE_HASH_FIELD] = hashing_info.source_hash
                layer_build_definition[MANIFEST_HASH_FIELD] = hashing_info.manifest_hash
                LOG.info("Updated source_hash and manifest_hash field in build.toml for layer with UUID %s", layer_uuid)

        self._filepath.write_text(tomlkit.dumps(cast(TOMLDocument, document)))

    def _read(self) -> None:
        """
        Reads build.toml file into array of build definition
        Each build definition will have empty function list, which will be populated from the current template.yaml file
        """
        LOG.debug("Instantiating build definitions")
        self._function_build_definitions = []
        self._layer_build_definitions = []
        document = {}
        try:
            txt = self._filepath.read_text()
            # .loads() returns a TOMLDocument,
            # and it behaves like a standard dictionary according to https://github.com/sdispater/tomlkit.
            # in tomlkit 0.7.2, the types are broken (tomlkit#128, #130, #134) so here we convert it to Dict.
            document = cast(Dict, tomlkit.loads(txt))
        except OSError:
            LOG.debug("No previous build graph found, generating new one")
        function_build_definitions_table = document.get(BuildGraph.FUNCTION_BUILD_DEFINITIONS, {})
        for function_build_definition_key in function_build_definitions_table:
            function_build_definition = _toml_table_to_function_build_definition(
                function_build_definition_key, function_build_definitions_table[function_build_definition_key]
            )
            self._function_build_definitions.append(function_build_definition)

        layer_build_definitions_table = document.get(BuildGraph.LAYER_BUILD_DEFINITIONS, {})
        for layer_build_definition_key in layer_build_definitions_table:
            layer_build_definition = _toml_table_to_layer_build_definition(
                layer_build_definition_key, layer_build_definitions_table[layer_build_definition_key]
            )
            self._layer_build_definitions.append(layer_build_definition)

    def _atomic_read(self) -> None:
        """
        Performs the _read() method with a global lock acquired
        It makes sure no other thread accesses build.toml when a read is happening
        """

        with BuildGraph.__toml_lock:
            self._read()

    def _write(self) -> None:
        """
        Writes build definition details into build.toml file, which would be used by the next build.
        build.toml file will contain the same information as build graph,
        function details will only be preserved as function names
        layer details will only be preserved as layer names
        """
        # convert build definition list into toml table
        function_build_definitions_table = tomlkit.table()
        for function_build_definition in self._function_build_definitions:
            build_definition_as_table = _function_build_definition_to_toml_table(function_build_definition)
            function_build_definitions_table.add(function_build_definition.uuid, build_definition_as_table)

        layer_build_definitions_table = tomlkit.table()
        for layer_build_definition in self._layer_build_definitions:
            build_definition_as_table = _layer_build_definition_to_toml_table(layer_build_definition)
            layer_build_definitions_table.add(layer_build_definition.uuid, build_definition_as_table)

        # create toml document and add build definitions
        document = tomlkit.document()
        document.add(tomlkit.comment("This file is auto generated by SAM CLI build command"))
        # we need to cast `Table` to `Item` because of tomlkit#135.
        document.add(BuildGraph.FUNCTION_BUILD_DEFINITIONS, cast(tomlkit.items.Item, function_build_definitions_table))
        document.add(BuildGraph.LAYER_BUILD_DEFINITIONS, cast(tomlkit.items.Item, layer_build_definitions_table))

        if not self._filepath.exists():
            open(self._filepath, "a+").close()  # pylint: disable=consider-using-with

        self._filepath.write_text(tomlkit.dumps(document))

    def _atomic_write(self) -> None:
        """
        Performs the _write() method with a global lock acquired
        It makes sure no other thread accesses build.toml when a write is happening
        """

        with BuildGraph.__toml_lock:
            self._write()


class AbstractBuildDefinition:
    """
    Abstract class for build definition
    Build definition holds information about each unique build
    """

    def __init__(
        self, source_hash: str, manifest_hash: str, env_vars: Optional[Dict] = None, architecture: str = X86_64
    ) -> None:
        self.uuid = str(uuid4())
        self.source_hash = source_hash
        self.manifest_hash = manifest_hash
        self._env_vars = env_vars if env_vars else {}
        self.architecture = architecture
        # following properties are used during build time and they don't serialize into build.toml file
        self.download_dependencies: bool = True

    @property
    def dependencies_dir(self) -> str:
        return str(os.path.join(DEFAULT_DEPENDENCIES_DIR, self.uuid))

    @property
    def env_vars(self) -> Dict:
        return deepcopy(self._env_vars)

    @abstractmethod
    def get_resource_full_paths(self) -> str:
        """Returns string representation of resources' full path information for this build definition"""


class LayerBuildDefinition(AbstractBuildDefinition):
    """
    LayerBuildDefinition holds information about each unique layer build
    """

    def __init__(
        self,
        full_path: str,
        codeuri: Optional[str],
        build_method: Optional[str],
        compatible_runtimes: Optional[List[str]],
        architecture: str,
        source_hash: str = "",
        manifest_hash: str = "",
        env_vars: Optional[Dict] = None,
    ):
        super().__init__(source_hash, manifest_hash, env_vars, architecture)
        self.full_path = full_path
        self.codeuri = codeuri
        self.build_method = build_method
        self.compatible_runtimes = compatible_runtimes
        # Note(xinhol): In our code, we assume "layer" is never None. We should refactor
        # this and move "layer" out of LayerBuildDefinition to take advantage of type check.
        self.layer: LayerVersion = None  # type: ignore

    def get_resource_full_paths(self) -> str:
        if not self.layer:
            LOG.debug("LayerBuildDefinition with uuid (%s) doesn't have a layer assigned to it", self.uuid)
            return ""
        return self.layer.full_path

    def __str__(self) -> str:
        return (
            f"LayerBuildDefinition({self.full_path}, {self.codeuri}, {self.source_hash}, {self.uuid}, "
            f"{self.build_method}, {self.compatible_runtimes}, {self.architecture}, {self.env_vars})"
        )

    def __eq__(self, other: Any) -> bool:
        """
        Checks equality of the layer build definition

        Parameters
        ----------
        other: Any
            other layer build definition to compare

        Returns
        -------
        bool
            True if both layer build definitions has same following properties, False otherwise
        """
        if not isinstance(other, LayerBuildDefinition):
            return False

        return (
            self.full_path == other.full_path
            and self.codeuri == other.codeuri
            and self.build_method == other.build_method
            and self.compatible_runtimes == other.compatible_runtimes
            and self.env_vars == other.env_vars
            and self.architecture == other.architecture
        )


class FunctionBuildDefinition(AbstractBuildDefinition):
    """
    LayerBuildDefinition holds information about each unique function build
    """

    def __init__(
        self,
        runtime: Optional[str],
        codeuri: Optional[str],
        imageuri: Optional[str],
        packagetype: str,
        architecture: str,
        metadata: Optional[Dict],
        handler: Optional[str],
        source_hash: str = "",
        manifest_hash: str = "",
        env_vars: Optional[Dict] = None,
    ) -> None:
        super().__init__(source_hash, manifest_hash, env_vars, architecture)
        self.runtime = runtime
        self.codeuri = codeuri
        self.imageuri = imageuri
        self.packagetype = packagetype
        self.handler = handler

        # Skip SAM Added metadata properties
        metadata_copied = deepcopy(metadata) if metadata else {}
        metadata_copied.pop(SAM_RESOURCE_ID_KEY, "")
        metadata_copied.pop(SAM_IS_NORMALIZED, "")
        self.metadata = metadata_copied

        self.functions: List[Function] = []

    def add_function(self, function: Function) -> None:
        self.functions.append(function)

    def get_function_name(self) -> str:
        self._validate_functions()
        return self.functions[0].name

    def get_handler_name(self) -> Optional[str]:
        self._validate_functions()
        return self.functions[0].handler

    def get_full_path(self) -> str:
        """
        Return the build identifier of the first function
        """
        self._validate_functions()
        return self.functions[0].full_path

    def get_build_dir(self, artifact_root_dir: str) -> str:
        """
        Return the directory path relative to root build directory
        """
        self._validate_functions()
        build_dir = self.functions[0].get_build_dir(artifact_root_dir)
        if is_experimental_enabled(ExperimentalFlag.BuildPerformance) and len(self.functions) > 1:
            # If there are multiple functions with the same build definition,
            # just put them into one single shared artifacts directory.
            build_dir = f"{build_dir}-{SHARED_CODEURI_SUFFIX}"
        return build_dir

    def get_resource_full_paths(self) -> str:
        """Returns list of functions' full path information as a list of str"""
        return ", ".join([function.full_path for function in self.functions])

    def _validate_functions(self) -> None:
        if not self.functions:
            raise InvalidBuildGraphException("Build definition doesn't have any function definition to build")

    def __str__(self) -> str:
        return (
            "BuildDefinition("
            f"{self.runtime}, {self.codeuri}, {self.packagetype}, {self.source_hash}, "
            f"{self.uuid}, {self.metadata}, {self.env_vars}, {self.architecture}, "
            f"{[f.functionname for f in self.functions]})"
        )

    def __eq__(self, other: Any) -> bool:
        """
        Checks equality of the function build definition

        Parameters
        ----------
        other: Any
            other function build definition to compare

        Returns
        -------
        bool
            True if both function build definitions has same following properties, False otherwise
        """
        if not isinstance(other, FunctionBuildDefinition):
            return False

        # each build with custom Makefile definition should be handled separately
        if self.metadata and self.metadata.get("BuildMethod", None) == "makefile":
            return False

        if self.metadata and self.metadata.get("BuildMethod", None) == "esbuild":
            # For esbuild, we need to check if handlers within the same CodeUri are the same
            # if they are different, it should create a separate build definition
            if self.handler != other.handler:
                return False

        if self.runtime in COMPILED_RUNTIMES:
            # For compiled languages, we need to check if handlers within the same CodeUri are the same
            # if they are different, it should create a separate build definition
            if self.handler != other.handler:
                return False

        return (
            self.runtime == other.runtime
            and self.codeuri == other.codeuri
            and self.imageuri == other.imageuri
            and self.packagetype == other.packagetype
            and self.metadata == other.metadata
            and self.env_vars == other.env_vars
            and self.architecture == other.architecture
        )
