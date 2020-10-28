from unittest import TestCase
from uuid import uuid4
from pathlib import Path

import tomlkit
from parameterized import parameterized

from samcli.lib.build.build_graph import (
    BuildDefinition,
    _build_definition_to_toml_table,
    CODE_URI_FIELD,
    RUNTIME_FIELD,
    METADATA_FIELD,
    FUNCTIONS_FIELD,
    _toml_table_to_build_definition,
    BuildGraph,
    InvalidBuildGraphException,
)
from samcli.lib.providers.provider import Function
from samcli.lib.utils import osutils


def generate_function(
    name="name",
    function_name="function_name",
    runtime="runtime",
    memory="memory",
    timeout="timeout",
    handler="handler",
    codeuri="codeuri",
    environment="environment",
    rolearn="rolearn",
    layers="layers",
    events="events",
    metadata={},
):
    return Function(
        name, function_name, runtime, memory, timeout, handler, codeuri, environment, rolearn, layers, events, metadata
    )


class TestConversionFunctions(TestCase):
    def test_build_definition_to_toml_table(self):
        build_definition = BuildDefinition("runtime", "codeuri", {"key": "value"})
        build_definition.add_function(generate_function())

        toml_table = _build_definition_to_toml_table(build_definition)

        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[RUNTIME_FIELD], build_definition.runtime)
        self.assertEqual(toml_table[METADATA_FIELD], build_definition.metadata)
        self.assertEqual(toml_table[FUNCTIONS_FIELD], [f.name for f in build_definition.functions])

    def test_toml_table_to_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[RUNTIME_FIELD] = "runtime"
        toml_table[METADATA_FIELD] = {"key": "value"}
        toml_table[FUNCTIONS_FIELD] = ["function1"]
        uuid = str(uuid4())

        build_definition = _toml_table_to_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.runtime, toml_table[RUNTIME_FIELD])
        self.assertEqual(build_definition.metadata, toml_table[METADATA_FIELD])
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.functions, [])


class TestBuildGraph(TestCase):
    CODEURI = "hello_world_python/"
    RUNTIME = "python3.8"
    METADATA = {"Test": "hello", "Test2": "world"}
    UUID = "3c1c254e-cd4b-4d94-8c74-7ab870b36063"

    BUILD_GRAPH_CONTENTS = f"""
    [build_definitions]
    [build_definitions.{UUID}]
    codeuri = "{CODEURI}"
    runtime = "{RUNTIME}"
    functions = ["HelloWorldPython", "HelloWorldPython2"]
    [build_definitions.{UUID}.metadata]
    Test = "{METADATA['Test']}"
    Test2 = "{METADATA['Test2']}"
    """

    def test_should_instantiate_first_time(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            build_graph1 = BuildGraph(str(build_dir.resolve()))
            build_graph1.clean_redundant_functions_and_update(True)

            build_graph2 = BuildGraph(str(build_dir.resolve()))

            self.assertEqual(build_graph1.get_build_definitions(), build_graph2.get_build_definitions())

    def test_should_instantiate_first_time_and_update(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            # create a build graph and persist it
            build_graph1 = BuildGraph(str(build_dir))
            build_definition1 = BuildDefinition(TestBuildGraph.RUNTIME, TestBuildGraph.CODEURI, TestBuildGraph.METADATA)
            function1 = generate_function(
                runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=TestBuildGraph.METADATA
            )
            build_graph1.put_build_definition(build_definition1, function1)
            build_graph1.clean_redundant_functions_and_update(True)

            # read previously persisted graph and compare
            build_graph2 = BuildGraph(str(build_dir))
            self.assertEqual(len(build_graph1.get_build_definitions()), len(build_graph2.get_build_definitions()))
            self.assertEqual(
                list(build_graph1.get_build_definitions())[0], list(build_graph2.get_build_definitions())[0]
            )

    def test_should_read_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))
            for build_definition in build_graph.get_build_definitions():
                self.assertEqual(build_definition.codeuri, TestBuildGraph.CODEURI)
                self.assertEqual(build_definition.runtime, TestBuildGraph.RUNTIME)
                self.assertEqual(build_definition.metadata, TestBuildGraph.METADATA)

    def test_functions_should_be_added_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_definition1 = BuildDefinition(TestBuildGraph.RUNTIME, TestBuildGraph.CODEURI, TestBuildGraph.METADATA)
            function1 = generate_function(
                runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=TestBuildGraph.METADATA
            )
            build_graph.put_build_definition(build_definition1, function1)

            self.assertTrue(len(build_graph.get_build_definitions()), 1)
            for build_definition in build_graph.get_build_definitions():
                self.assertTrue(len(build_definition.functions), 1)
                self.assertTrue(build_definition.functions[0], function1)
                self.assertEqual(build_definition.uuid, TestBuildGraph.UUID)

            build_definition2 = BuildDefinition("another_runtime", "another_codeuri", None)
            function2 = generate_function(name="another_function")
            build_graph.put_build_definition(build_definition2, function2)
            self.assertTrue(len(build_graph.get_build_definitions()), 2)


class TestBuildDefinition(TestCase):
    def test_single_function_should_return_function_and_handler_name(self):
        build_definition = BuildDefinition("runtime", "codeuri", "metadata")
        build_definition.add_function(generate_function())

        self.assertEqual(build_definition.get_handler_name(), "handler")
        self.assertEqual(build_definition.get_function_name(), "name")

    def test_no_function_should_raise_exception(self):
        build_definition = BuildDefinition("runtime", "codeuri", "metadata")

        self.assertRaises(InvalidBuildGraphException, build_definition.get_handler_name)
        self.assertRaises(InvalidBuildGraphException, build_definition.get_function_name)

    def test_same_runtime_codeuri_metadata_should_reflect_as_same_object(self):
        build_definition1 = BuildDefinition("runtime", "codeuri", {"key": "value"})
        build_definition2 = BuildDefinition("runtime", "codeuri", {"key": "value"})

        self.assertEqual(build_definition1, build_definition2)

    @parameterized.expand(
        [
            ("runtime", "codeuri", ({"key": "value"}), "runtime", "codeuri", ({"key": "different_value"})),
            ("runtime", "codeuri", ({"key": "value"}), "different_runtime", "codeuri", ({"key": "value"})),
            ("runtime", "codeuri", ({"key": "value"}), "runtime", "different_codeuri", ({"key": "value"})),
            # custom build method with Makefile definition should always be identified as different
            ("runtime", "codeuri", ({"BuildMethod": "makefile"}), "runtime", "codeuri", ({"BuildMethod": "makefile"})),
        ]
    )
    def test_different_runtime_codeuri_metadata_should_not_reflect_as_same_object(
        self, runtime1, codeuri1, metadata1, runtime2, codeuri2, metadata2
    ):
        build_definition1 = BuildDefinition(runtime1, codeuri1, metadata1)
        build_definition2 = BuildDefinition(runtime2, codeuri2, metadata2)

        self.assertNotEqual(build_definition1, build_definition2)

    def test_euqality_with_another_object(self):
        build_definition = BuildDefinition("runtime", "codeuri", None)
        self.assertNotEqual(build_definition, {})

    def test_str_representation(self):
        build_definition = BuildDefinition("runtime", "codeuri", None)
        self.assertEqual(str(build_definition), f"BuildDefinition(runtime, codeuri, {build_definition.uuid}, {{}}, [])")
