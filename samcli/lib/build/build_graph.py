"""
Holds classes and utility methods related to build graph
"""

import logging
from pathlib import Path
from uuid import uuid4

import tomlkit

LOG = logging.getLogger(__name__)

DEFAULT_BUILD_GRAPH_FILE_NAME = "build.toml"

# filed names for the toml table
CODE_URI_FIELD = "codeuri"
RUNTIME_FIELD = "runtime"
METADATA_FIELD = "metadata"
FUNCTIONS_FIELD = "functions"


class InvalidBuildGraphException(Exception):

    def __init__(self, msg):
        Exception.__init__(self, msg)


def _build_definition_to_toml_table(build_definition):
    """
    Converts given build_definition into toml table representation

    :param build_definition: BuildDefinition
    :return: toml table of BuildDefinition
    """
    toml_table = tomlkit.table()
    toml_table[CODE_URI_FIELD] = build_definition.codeuri
    toml_table[RUNTIME_FIELD] = build_definition.runtime
    toml_table[FUNCTIONS_FIELD] = \
        list(map(lambda f: f.name, build_definition.functions))

    if build_definition.metadata:
        toml_table[METADATA_FIELD] = build_definition.metadata

    return toml_table


def _toml_table_to_build_definition(uuid, toml_table):
    """
    Converts given toml table into BuildDefinition instance

    :param uuid: key of the toml_table instance
    :param toml_table: build definition as toml table
    :return: BuildDefinition of given toml table
    """
    build_definition = BuildDefinition(toml_table[RUNTIME_FIELD],
                                       toml_table[CODE_URI_FIELD],
                                       dict(toml_table.get(METADATA_FIELD, {})))
    build_definition.uuid = uuid
    return build_definition


class BuildGraph:
    """
    Contains list of build definitions, with ability to read and write them into build.toml file
    """

    # global table build definitions key
    BUILD_DEFINITIONS = "build_definitions"

    def __init__(self, build_dir):
        # put build.toml file inside .aws-sam folder
        self._filepath = Path(build_dir).parent.joinpath(DEFAULT_BUILD_GRAPH_FILE_NAME)
        self._build_definitions = []
        self._read()

    def get_build_definitions(self):
        return tuple(self._build_definitions)

    def put_build_definition(self, build_definition, function):
        """
        Puts the newly read build definition into existing build graph.
        If graph already contains a build definition which is same as the newly passed one, then it will add
        the function to the existing one, discarding the new one

        If graph doesn't contain such unique build definition, it will be added to the current build graph

        :param build_definition: build definition which is newly read from template.yaml file
        :param function: function details for this build definition
        """
        if build_definition in self._build_definitions:
            previous_build_definition = self._build_definitions[self._build_definitions.index(build_definition)]
            LOG.debug("Same build definition found, adding function (Previous: %s, Current: %s, Function: %s)",
                      previous_build_definition, build_definition, function)
            previous_build_definition.add_function(function)
        else:
            LOG.debug("Unique build definition found, adding as new (Build Definition: %s, Function: %s)",
                      build_definition, function)
            build_definition.add_function(function)
            self._build_definitions.append(build_definition)

    def clean_redundant_functions_and_update(self, persist):
        """
        Removes build definitions which doesn't have any function in it, which means these build definitions
        are no longer used, and they can be deleted

        If persist parameter is given True, build graph is written to .aws-sam/build.toml file
        """
        self._build_definitions[:] = [bd for bd in self._build_definitions if len(bd.functions) > 0]
        if persist:
            self._write()

    def _read(self):
        """
        Reads build.toml file into array of build definition
        Each build definition will have empty function list, which will be populated from the current template.yaml file
        """
        LOG.debug("Instantiating build definitions")
        self._build_definitions = []
        document = {}
        try:
            txt = self._filepath.read_text()
            document = tomlkit.loads(txt)
        except OSError:
            LOG.debug("No previous build graph found, generating new one")
        build_definitions_table = document.get(BuildGraph.BUILD_DEFINITIONS, [])
        for build_definition_key in build_definitions_table:
            build_definition = _toml_table_to_build_definition(build_definition_key,
                                                               build_definitions_table[build_definition_key])
            self._build_definitions.append(build_definition)

        return self._build_definitions

    def _write(self):
        """
        Writes build definition details into build.toml file, which would be used by the next build.
        build.toml file will contain the same information as build graph,
        function details will only be preserved as function names
        """
        # convert build definition list into toml table
        build_definitions_table = tomlkit.table()
        for build_definition in self._build_definitions:
            build_definition_as_table = _build_definition_to_toml_table(build_definition)
            build_definitions_table.add(build_definition.uuid, build_definition_as_table)

        # create toml document and add build definitions
        document = tomlkit.document()
        document.add(tomlkit.comment("This file is auto generated by SAM CLI build command"))
        document.add(BuildGraph.BUILD_DEFINITIONS, build_definitions_table)

        if not self._filepath.exists():
            open(self._filepath, "a+").close()

        self._filepath.write_text(tomlkit.dumps(document))


class BuildDefinition:
    """
    Build definition holds information about each unique build
    """

    def __init__(self, runtime, codeuri, metadata):
        self.runtime = runtime
        self.codeuri = codeuri
        self.metadata = metadata if metadata else {}
        self.uuid = str(uuid4())
        self.functions = []

    def add_function(self, function):
        self.functions.append(function)

    def get_function_name(self):
        self._validate_functions()
        return self.functions[0].name

    def get_handler_name(self):
        self._validate_functions()
        return self.functions[0].handler

    def _validate_functions(self):
        if not self.functions:
            raise InvalidBuildGraphException("Build definition doesn't have any function definition to build")

    def __str__(self):
        return f"BuildDefinition({self.runtime}, {self.codeuri}, {self.uuid}, {self.metadata}, " \
               f"{[f.functionname for f in self.functions]})"

    def __eq__(self, other):
        """
        Checks uniqueness of the build definition

        :param other: other build definition to compare
        :return: True if both build definitions has same following properties, False otherwise
        """
        if not isinstance(other, BuildDefinition):
            return False

        # each build with custom Makefile definition should be handled separately
        if self.metadata and self.metadata.get("BuildMethod", None) == "makefile":
            return False

        return self.runtime == other.runtime \
               and self.codeuri == other.codeuri \
               and self.metadata == other.metadata
