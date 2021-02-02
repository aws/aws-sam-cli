"""
Holds classes and utility methods related to build graph
"""

import logging
from pathlib import Path
from typing import Tuple, List, Any, Optional
from uuid import uuid4

import tomlkit

from samcli.lib.build.exceptions import InvalidBuildGraphException
from samcli.lib.providers.provider import Function, LayerVersion
from samcli.lib.utils.packagetype import ZIP

LOG = logging.getLogger(__name__)

DEFAULT_BUILD_GRAPH_FILE_NAME = "build.toml"

# filed names for the toml table
PACKAGETYPE_FIELD = "packagetype"
CODE_URI_FIELD = "codeuri"
RUNTIME_FIELD = "runtime"
METADATA_FIELD = "metadata"
FUNCTIONS_FIELD = "functions"
SOURCE_MD5_FIELD = "source_md5"
LAYER_NAME_FIELD = "layer_name"
BUILD_METHOD_FIELD = "build_method"
COMPATIBLE_RUNTIMES_FIELD = "compatible_runtimes"
LAYER_FIELD = "layer"


def _function_build_definition_to_toml_table(
    function_build_definition: "FunctionBuildDefinition",
) -> tomlkit.items.Table:
    """
    Converts given function_build_definition into toml table representation

    Parameters
    ----------
    function_build_definition: FunctionBuildDefinition
        FunctionBuildDefinition which will be converted into toml table

    Returns
    -------
    tomlkit.items.Table
        toml table of FunctionBuildDefinition
    """
    toml_table = tomlkit.table()
    if function_build_definition.packagetype == ZIP:
        toml_table[CODE_URI_FIELD] = function_build_definition.codeuri
        toml_table[RUNTIME_FIELD] = function_build_definition.runtime
        toml_table[SOURCE_MD5_FIELD] = function_build_definition.source_md5
    toml_table[PACKAGETYPE_FIELD] = function_build_definition.packagetype
    toml_table[FUNCTIONS_FIELD] = [f.name for f in function_build_definition.functions]

    if function_build_definition.metadata:
        toml_table[METADATA_FIELD] = function_build_definition.metadata

    return toml_table


def _toml_table_to_function_build_definition(uuid: str, toml_table: tomlkit.items.Table) -> "FunctionBuildDefinition":
    """
    Converts given toml table into FunctionBuildDefinition instance

    Parameters
    ----------
    uuid: str
        key of the function toml_table instance
    toml_table: tomlkit.items.Table
        function build definition as toml table

    Returns
    -------
    FunctionBuildDefinition
        FunctionBuildDefinition of given toml table
    """
    function_build_definition = FunctionBuildDefinition(
        toml_table.get(RUNTIME_FIELD),
        toml_table.get(CODE_URI_FIELD),
        toml_table.get(PACKAGETYPE_FIELD, ZIP),
        dict(toml_table.get(METADATA_FIELD, {})),
        toml_table.get(SOURCE_MD5_FIELD, ""),
    )
    function_build_definition.uuid = uuid
    return function_build_definition


def _layer_build_definition_to_toml_table(layer_build_definition: "LayerBuildDefinition") -> tomlkit.items.Table:
    """
    Converts given layer_build_definition into toml table representation

    Parameters
    ----------
    layer_build_definition: LayerBuildDefinition
        LayerBuildDefinition which will be converted into toml table

    Returns
    -------
    tomlkit.items.Table
        toml table of LayerBuildDefinition
    """
    toml_table = tomlkit.table()
    toml_table[LAYER_NAME_FIELD] = layer_build_definition.name
    toml_table[CODE_URI_FIELD] = layer_build_definition.codeuri
    toml_table[BUILD_METHOD_FIELD] = layer_build_definition.build_method
    toml_table[COMPATIBLE_RUNTIMES_FIELD] = layer_build_definition.compatible_runtimes
    toml_table[SOURCE_MD5_FIELD] = layer_build_definition.source_md5
    toml_table[LAYER_FIELD] = layer_build_definition.layer.name

    return toml_table


def _toml_table_to_layer_build_definition(uuid: str, toml_table: tomlkit.items.Table) -> "LayerBuildDefinition":
    """
    Converts given toml table into LayerBuildDefinition instance

    Parameters
    ----------
    uuid: str
        key of the toml_table instance
    toml_table:  tomlkit.items.Table
        layer build definition as toml table

    Returns
    -------
    LayerBuildDefinition
        LayerBuildDefinition of given toml table
    """
    layer_build_definition = LayerBuildDefinition(
        toml_table[LAYER_NAME_FIELD],
        toml_table[CODE_URI_FIELD],
        toml_table[BUILD_METHOD_FIELD],
        toml_table[COMPATIBLE_RUNTIMES_FIELD],
        toml_table.get(SOURCE_MD5_FIELD, ""),
    )
    layer_build_definition.uuid = uuid
    return layer_build_definition


class BuildGraph:
    """
    Contains list of build definitions, with ability to read and write them into build.toml file
    """

    # global table build definitions key
    FUNCTION_BUILD_DEFINITIONS = "function_build_definitions"
    LAYER_BUILD_DEFINITIONS = "layer_build_definitions"

    def __init__(self, build_dir: str) -> None:
        # put build.toml file inside .aws-sam folder
        self._filepath = Path(build_dir).parent.joinpath(DEFAULT_BUILD_GRAPH_FILE_NAME)
        self._function_build_definitions: List["FunctionBuildDefinition"] = []
        self._layer_build_definitions: List["LayerBuildDefinition"] = []
        self._read()

    def get_function_build_definitions(self) -> Tuple["FunctionBuildDefinition", ...]:
        return tuple(self._function_build_definitions)

    def get_layer_build_definitions(self) -> Tuple["LayerBuildDefinition", ...]:
        return tuple(self._layer_build_definitions)

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
            self._write()

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
            document = tomlkit.loads(txt)
        except OSError:
            LOG.debug("No previous build graph found, generating new one")
        function_build_definitions_table = document.get(BuildGraph.FUNCTION_BUILD_DEFINITIONS, [])
        for function_build_definition_key in function_build_definitions_table:
            function_build_definition = _toml_table_to_function_build_definition(
                function_build_definition_key, function_build_definitions_table[function_build_definition_key]
            )
            self._function_build_definitions.append(function_build_definition)

        layer_build_definitions_table = document.get(BuildGraph.LAYER_BUILD_DEFINITIONS, [])
        for layer_build_definition_key in layer_build_definitions_table:
            layer_build_definition = _toml_table_to_layer_build_definition(
                layer_build_definition_key, layer_build_definitions_table[layer_build_definition_key]
            )
            self._layer_build_definitions.append(layer_build_definition)

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
        document.add(BuildGraph.FUNCTION_BUILD_DEFINITIONS, function_build_definitions_table)
        document.add(BuildGraph.LAYER_BUILD_DEFINITIONS, layer_build_definitions_table)

        if not self._filepath.exists():
            open(self._filepath, "a+").close()

        self._filepath.write_text(tomlkit.dumps(document))


class AbstractBuildDefinition:
    """
    Abstract class for build definition
    Build definition holds information about each unique build
    """

    def __init__(self, source_md5: str) -> None:
        self.uuid = str(uuid4())
        self.source_md5 = source_md5


class LayerBuildDefinition(AbstractBuildDefinition):
    """
    LayerBuildDefinition holds information about each unique layer build
    """

    def __init__(
        self, name: str, codeuri: str, build_method: str, compatible_runtimes: List[str], source_md5: str = ""
    ):
        super().__init__(source_md5)
        self.name = name
        self.codeuri = codeuri
        self.build_method = build_method
        self.compatible_runtimes = compatible_runtimes
        # Note(xinhol): In our code, we assume "layer" is never None. We should refactor
        # this and move "layer" out of LayerBuildDefinition to take advantage of type check.
        self.layer: LayerVersion = None  # type: ignore

    def __str__(self) -> str:
        return (
            f"LayerBuildDefinition({self.name}, {self.codeuri}, {self.source_md5}, {self.uuid}, "
            f"{self.build_method}, {self.compatible_runtimes}, {self.layer.name})"
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
            self.name == other.name
            and self.codeuri == other.codeuri
            and self.build_method == other.build_method
            and self.compatible_runtimes == other.compatible_runtimes
        )


class FunctionBuildDefinition(AbstractBuildDefinition):
    """
    LayerBuildDefinition holds information about each unique function build
    """

    def __init__(
        self, runtime: str, codeuri: str, packagetype: str, metadata: Optional[dict], source_md5: str = ""
    ) -> None:
        super().__init__(source_md5)
        self.runtime = runtime
        self.codeuri = codeuri
        self.packagetype = packagetype
        self.metadata = metadata if metadata else {}
        self.functions: List[Function] = []

    def add_function(self, function: Function) -> None:
        self.functions.append(function)

    def get_function_name(self) -> str:
        self._validate_functions()
        return self.functions[0].name

    def get_handler_name(self) -> Optional[str]:
        self._validate_functions()
        return self.functions[0].handler

    def _validate_functions(self) -> None:
        if not self.functions:
            raise InvalidBuildGraphException("Build definition doesn't have any function definition to build")

    def __str__(self) -> str:
        return (
            "BuildDefinition("
            f"{self.runtime}, {self.codeuri}, {self.packagetype}, {self.source_md5}, {self.uuid}, {self.metadata}, "
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

        return (
            self.runtime == other.runtime
            and self.codeuri == other.codeuri
            and self.packagetype == other.packagetype
            and self.metadata == other.metadata
        )
