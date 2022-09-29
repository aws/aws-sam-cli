import os.path
from unittest import TestCase
from unittest.mock import patch, Mock
from uuid import uuid4
from pathlib import Path

import tomlkit
from samcli.lib.utils.architecture import X86_64, ARM64
from parameterized import parameterized
from typing import Dict, cast

from samcli.lib.build.build_graph import (
    FunctionBuildDefinition,
    _function_build_definition_to_toml_table,
    _layer_build_definition_to_toml_table,
    CODE_URI_FIELD,
    RUNTIME_FIELD,
    PACKAGETYPE_FIELD,
    METADATA_FIELD,
    FUNCTIONS_FIELD,
    SOURCE_HASH_FIELD,
    ENV_VARS_FIELD,
    LAYER_NAME_FIELD,
    BUILD_METHOD_FIELD,
    COMPATIBLE_RUNTIMES_FIELD,
    LAYER_FIELD,
    ARCHITECTURE_FIELD,
    _toml_table_to_function_build_definition,
    _toml_table_to_layer_build_definition,
    BuildGraph,
    InvalidBuildGraphException,
    LayerBuildDefinition,
    MANIFEST_HASH_FIELD,
    BuildHashingInformation,
    HANDLER_FIELD,
)
from samcli.lib.providers.provider import Function, LayerVersion
from samcli.lib.utils import osutils
from samcli.lib.utils.packagetype import ZIP


def generate_function(
    function_id="name",
    name="name",
    function_name="function_name",
    runtime="runtime",
    memory="memory",
    timeout="timeout",
    handler="handler",
    imageuri="imageuri",
    packagetype=ZIP,
    imageconfig="imageconfig",
    codeuri="codeuri",
    environment="environment",
    rolearn="rolearn",
    layers="layers",
    events="events",
    codesign_config_arn="codesign_config_arn",
    metadata=None,
    inlinecode=None,
    architectures=[X86_64],
    stack_path="",
):
    if metadata is None:
        metadata = {}

    return Function(
        function_id,
        name,
        function_name,
        runtime,
        memory,
        timeout,
        handler,
        imageuri,
        packagetype,
        imageconfig,
        codeuri,
        environment,
        rolearn,
        layers,
        events,
        metadata,
        inlinecode,
        codesign_config_arn,
        architectures,
        stack_path,
    )


def generate_layer(
    arn="arn:aws:lambda:region:account-id:layer:layer-name:1",
    codeuri="codeuri",
    compatible_runtimes=None,
    metadata=None,
    stack_path="",
):
    if compatible_runtimes is None:
        compatible_runtimes = ["runtime"]
    if metadata is None:
        metadata = {}

    return LayerVersion(arn, codeuri, compatible_runtimes, metadata, stack_path)


class TestConversionFunctions(TestCase):
    def test_function_build_definition_to_toml_table(self):
        build_definition = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            ZIP,
            X86_64,
            {"key": "value"},
            "source_hash",
            "manifest_hash",
            env_vars={"env_vars": "value1"},
        )
        build_definition.add_function(generate_function())

        toml_table = _function_build_definition_to_toml_table(build_definition)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[PACKAGETYPE_FIELD], build_definition.packagetype)
        self.assertEqual(toml_table[RUNTIME_FIELD], build_definition.runtime)
        self.assertEqual(toml_table[METADATA_FIELD], build_definition.metadata)
        self.assertEqual(toml_table[FUNCTIONS_FIELD], [f.name for f in build_definition.functions])
        self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ENV_VARS_FIELD], build_definition.env_vars)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_layer_build_definition_to_toml_table(self):
        build_definition = LayerBuildDefinition(
            "name",
            "codeuri",
            "method",
            ["runtime"],
            ARM64,
            "source_hash",
            "manifest_hash",
            env_vars={"env_vars": "value"},
        )
        build_definition.layer = generate_function()

        toml_table = _layer_build_definition_to_toml_table(build_definition)

        self.assertEqual(toml_table[LAYER_NAME_FIELD], build_definition.full_path)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[BUILD_METHOD_FIELD], build_definition.build_method)
        self.assertEqual(toml_table[COMPATIBLE_RUNTIMES_FIELD], build_definition.compatible_runtimes)
        self.assertEqual(toml_table[LAYER_FIELD], build_definition.layer.name)
        self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ENV_VARS_FIELD], build_definition.env_vars)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_toml_table_to_function_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[RUNTIME_FIELD] = "runtime"
        toml_table[PACKAGETYPE_FIELD] = ZIP
        toml_table[METADATA_FIELD] = {"key": "value"}
        toml_table[FUNCTIONS_FIELD] = ["function1"]
        toml_table[SOURCE_HASH_FIELD] = "source_hash"
        toml_table[MANIFEST_HASH_FIELD] = "manifest_hash"
        toml_table[ENV_VARS_FIELD] = {"env_vars": "value"}
        toml_table[ARCHITECTURE_FIELD] = X86_64
        uuid = str(uuid4())

        build_definition = _toml_table_to_function_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.packagetype, toml_table[PACKAGETYPE_FIELD])
        self.assertEqual(build_definition.runtime, toml_table[RUNTIME_FIELD])
        self.assertEqual(build_definition.metadata, toml_table[METADATA_FIELD])
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.functions, [])
        self.assertEqual(build_definition.source_hash, toml_table[SOURCE_HASH_FIELD])
        self.assertEqual(build_definition.manifest_hash, toml_table[MANIFEST_HASH_FIELD])
        self.assertEqual(build_definition.env_vars, toml_table[ENV_VARS_FIELD])
        self.assertEqual(build_definition.architecture, toml_table[ARCHITECTURE_FIELD])

    def test_toml_table_to_layer_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[LAYER_NAME_FIELD] = "name"
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[BUILD_METHOD_FIELD] = "method"
        toml_table[COMPATIBLE_RUNTIMES_FIELD] = "runtime"
        toml_table[COMPATIBLE_RUNTIMES_FIELD] = "layer1"
        toml_table[SOURCE_HASH_FIELD] = "source_hash"
        toml_table[MANIFEST_HASH_FIELD] = "manifest_hash"
        toml_table[ENV_VARS_FIELD] = {"env_vars": "value"}
        toml_table[ARCHITECTURE_FIELD] = ARM64
        uuid = str(uuid4())

        build_definition = _toml_table_to_layer_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.full_path, toml_table[LAYER_NAME_FIELD])
        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.build_method, toml_table[BUILD_METHOD_FIELD])
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.compatible_runtimes, toml_table[COMPATIBLE_RUNTIMES_FIELD])
        self.assertEqual(build_definition.layer, None)
        self.assertEqual(build_definition.source_hash, toml_table[SOURCE_HASH_FIELD])
        self.assertEqual(build_definition.manifest_hash, toml_table[MANIFEST_HASH_FIELD])
        self.assertEqual(build_definition.env_vars, toml_table[ENV_VARS_FIELD])
        self.assertEqual(build_definition.architecture, toml_table[ARCHITECTURE_FIELD])

    def test_minimal_function_build_definition_to_toml_table(self):
        build_definition = FunctionBuildDefinition("runtime", "codeuri", ZIP, X86_64, {"key": "value"}, "handler")
        build_definition.add_function(generate_function())

        toml_table = _function_build_definition_to_toml_table(build_definition)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[PACKAGETYPE_FIELD], build_definition.packagetype)
        self.assertEqual(toml_table[RUNTIME_FIELD], build_definition.runtime)
        self.assertEqual(toml_table[METADATA_FIELD], build_definition.metadata)
        self.assertEqual(toml_table[HANDLER_FIELD], build_definition.handler)
        self.assertEqual(toml_table[FUNCTIONS_FIELD], [f.name for f in build_definition.functions])
        if build_definition.source_hash:
            self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_minimal_layer_build_definition_to_toml_table(self):
        build_definition = LayerBuildDefinition("name", "codeuri", "method", "runtime", ARM64)
        build_definition.layer = generate_function()

        toml_table = _layer_build_definition_to_toml_table(build_definition)

        self.assertEqual(toml_table[LAYER_NAME_FIELD], build_definition.full_path)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[BUILD_METHOD_FIELD], build_definition.build_method)
        self.assertEqual(toml_table[COMPATIBLE_RUNTIMES_FIELD], build_definition.compatible_runtimes)
        self.assertEqual(toml_table[LAYER_FIELD], build_definition.layer.name)
        if build_definition.source_hash:
            self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_minimal_toml_table_to_function_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[RUNTIME_FIELD] = "runtime"
        toml_table[FUNCTIONS_FIELD] = ["function1"]
        uuid = str(uuid4())

        build_definition = _toml_table_to_function_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.packagetype, ZIP)
        self.assertEqual(build_definition.runtime, toml_table[RUNTIME_FIELD])
        self.assertEqual(build_definition.metadata, {})
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.functions, [])
        self.assertEqual(build_definition.source_hash, "")
        self.assertEqual(build_definition.manifest_hash, "")
        self.assertEqual(build_definition.env_vars, {})
        self.assertEqual(build_definition.architecture, X86_64)

    def test_minimal_toml_table_to_layer_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[LAYER_NAME_FIELD] = "name"
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[BUILD_METHOD_FIELD] = "method"
        toml_table[COMPATIBLE_RUNTIMES_FIELD] = "runtime"
        uuid = str(uuid4())

        build_definition = _toml_table_to_layer_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.full_path, toml_table[LAYER_NAME_FIELD])
        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.build_method, toml_table[BUILD_METHOD_FIELD])
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.compatible_runtimes, toml_table[COMPATIBLE_RUNTIMES_FIELD])
        self.assertEqual(build_definition.layer, None)
        self.assertEqual(build_definition.source_hash, "")
        self.assertEqual(build_definition.manifest_hash, "")
        self.assertEqual(build_definition.env_vars, {})
        self.assertEqual(build_definition.architecture, X86_64)


class TestBuildGraph(TestCase):
    CODEURI = "hello_world_python/"
    LAYER_CODEURI = "sum_layer/"
    LAYER_NAME = "SumLayer"
    ZIP = ZIP
    RUNTIME = "python3.8"
    LAYER_RUNTIME = "nodejs12.x"
    METADATA = {"Test": "hello", "Test2": "world"}
    UUID = "3c1c254e-cd4b-4d94-8c74-7ab870b36063"
    LAYER_UUID = "7dnc257e-cd4b-4d94-8c74-7ab870b3abc3"
    SOURCE_HASH = "cae49aa393d669e850bd49869905099d"
    MANIFEST_HASH = "rty87gh393d669e850bd49869905099e"
    ENV_VARS = {"env_vars": "value"}
    ARCHITECTURE_FIELD = ARM64
    LAYER_ARCHITECTURE = X86_64
    HANDLER = "app.handler"

    BUILD_GRAPH_CONTENTS = f"""
    [function_build_definitions]
    [function_build_definitions.{UUID}]
    codeuri = "{CODEURI}"
    runtime = "{RUNTIME}"
    source_hash = "{SOURCE_HASH}"
    manifest_hash = "{MANIFEST_HASH}"
    packagetype = "{ZIP}"
    architecture = "{ARCHITECTURE_FIELD}"
    handler = "{HANDLER}"
    functions = ["HelloWorldPython", "HelloWorld2Python"]
    [function_build_definitions.{UUID}.metadata]
    Test = "{METADATA['Test']}"
    Test2 = "{METADATA['Test2']}"
    [function_build_definitions.{UUID}.env_vars]
    env_vars = "{ENV_VARS['env_vars']}"

    [layer_build_definitions]
    [layer_build_definitions.{LAYER_UUID}]
    layer_name = "{LAYER_NAME}"
    codeuri = "{LAYER_CODEURI}"
    build_method = "{LAYER_RUNTIME}"
    compatible_runtimes = ["{LAYER_RUNTIME}"]
    architecture = "{LAYER_ARCHITECTURE}"
    source_hash = "{SOURCE_HASH}"
    manifest_hash = "{MANIFEST_HASH}"
    layer = "SumLayer"
    [layer_build_definitions.{LAYER_UUID}.env_vars]
    env_vars = "{ENV_VARS['env_vars']}"
    """

    def test_should_instantiate_first_time(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            build_graph1 = BuildGraph(str(build_dir.resolve()))
            build_graph1.clean_redundant_definitions_and_update(True)

            build_graph2 = BuildGraph(str(build_dir.resolve()))

            self.assertEqual(
                build_graph1.get_function_build_definitions(), build_graph2.get_function_build_definitions()
            )
            self.assertEqual(build_graph1.get_layer_build_definitions(), build_graph2.get_layer_build_definitions())

    def test_should_instantiate_first_time_and_update(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            # create a build graph and persist it
            build_graph1 = BuildGraph(str(build_dir))
            function_build_definition1 = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            function1 = generate_function(
                runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=TestBuildGraph.METADATA
            )
            build_graph1.put_function_build_definition(function_build_definition1, function1)
            layer_build_definition1 = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            layer1 = generate_layer(
                compatible_runtimes=[TestBuildGraph.RUNTIME],
                codeuri=TestBuildGraph.LAYER_CODEURI,
                metadata=TestBuildGraph.METADATA,
            )
            build_graph1.put_layer_build_definition(layer_build_definition1, layer1)

            build_graph1.clean_redundant_definitions_and_update(True)

            # read previously persisted graph and compare
            build_graph2 = BuildGraph(str(build_dir))
            self.assertEqual(
                len(build_graph1.get_function_build_definitions()), len(build_graph2.get_function_build_definitions())
            )
            self.assertEqual(
                len(build_graph1.get_layer_build_definitions()), len(build_graph2.get_layer_build_definitions())
            )
            self.assertEqual(
                list(build_graph1.get_function_build_definitions())[0],
                list(build_graph2.get_function_build_definitions())[0],
            )
            self.assertEqual(
                list(build_graph1.get_layer_build_definitions())[0],
                list(build_graph2.get_layer_build_definitions())[0],
            )

    def test_should_read_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))
            for function_build_definition in build_graph.get_function_build_definitions():
                self.assertEqual(function_build_definition.codeuri, TestBuildGraph.CODEURI)
                self.assertEqual(function_build_definition.runtime, TestBuildGraph.RUNTIME)
                self.assertEqual(function_build_definition.packagetype, TestBuildGraph.ZIP)
                self.assertEqual(function_build_definition.architecture, TestBuildGraph.ARCHITECTURE_FIELD)
                self.assertEqual(function_build_definition.metadata, TestBuildGraph.METADATA)
                self.assertEqual(function_build_definition.source_hash, TestBuildGraph.SOURCE_HASH)
                self.assertEqual(function_build_definition.manifest_hash, TestBuildGraph.MANIFEST_HASH)
                self.assertEqual(function_build_definition.env_vars, TestBuildGraph.ENV_VARS)

            for layer_build_definition in build_graph.get_layer_build_definitions():
                self.assertEqual(layer_build_definition.full_path, TestBuildGraph.LAYER_NAME)
                self.assertEqual(layer_build_definition.codeuri, TestBuildGraph.LAYER_CODEURI)
                self.assertEqual(layer_build_definition.build_method, TestBuildGraph.LAYER_RUNTIME)
                self.assertEqual(layer_build_definition.source_hash, TestBuildGraph.SOURCE_HASH)
                self.assertEqual(layer_build_definition.manifest_hash, TestBuildGraph.MANIFEST_HASH)
                self.assertEqual(layer_build_definition.compatible_runtimes, [TestBuildGraph.LAYER_RUNTIME])
                self.assertEqual(layer_build_definition.env_vars, TestBuildGraph.ENV_VARS)

    def test_functions_should_be_added_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_definition1 = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            function1 = generate_function(
                runtime=TestBuildGraph.RUNTIME,
                codeuri=TestBuildGraph.CODEURI,
                metadata=TestBuildGraph.METADATA,
            )
            build_graph.put_function_build_definition(build_definition1, function1)

            build_definitions = build_graph.get_function_build_definitions()
            self.assertEqual(len(build_definitions), 1)
            self.assertEqual(len(build_definitions[0].functions), 1)
            self.assertEqual(build_definitions[0].functions[0], function1)
            self.assertEqual(build_definitions[0].uuid, TestBuildGraph.UUID)

            build_definition2 = FunctionBuildDefinition(
                "another_runtime",
                "another_codeuri",
                TestBuildGraph.ZIP,
                ARM64,
                None,
                "app.handler",
                "another_source_hash",
                "another_manifest_hash",
                {"env_vars": "value2"},
            )
            function2 = generate_function(name="another_function")
            build_graph.put_function_build_definition(build_definition2, function2)

            build_definitions = build_graph.get_function_build_definitions()
            self.assertEqual(len(build_definitions), 2)
            self.assertEqual(len(build_definitions[1].functions), 1)
            self.assertEqual(build_definitions[1].functions[0], function2)

    def test_layers_should_be_added_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_definition1 = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.LAYER_ARCHITECTURE,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            layer1 = generate_layer(
                compatible_runtimes=[TestBuildGraph.RUNTIME],
                codeuri=TestBuildGraph.LAYER_CODEURI,
                metadata=TestBuildGraph.METADATA,
            )
            build_graph.put_layer_build_definition(build_definition1, layer1)

            build_definitions = build_graph.get_layer_build_definitions()
            self.assertEqual(len(build_definitions), 1)
            self.assertEqual(build_definitions[0].layer, layer1)
            self.assertEqual(build_definitions[0].uuid, TestBuildGraph.LAYER_UUID)

            build_definition2 = LayerBuildDefinition(
                "another_layername",
                "another_codeuri",
                "another_runtime",
                ["another_runtime"],
                "another_source_hash",
                "another_manifest_hash",
                {"env_vars": "value2"},
            )
            layer2 = generate_layer(arn="arn:aws:lambda:region:account-id:layer:another-layer-name:1")
            build_graph.put_layer_build_definition(build_definition2, layer2)

            build_definitions = build_graph.get_layer_build_definitions()
            self.assertEqual(len(build_definitions), 2)
            self.assertEqual(build_definitions[1].layer, layer2)

    @patch("samcli.lib.build.build_graph.BuildGraph._write_source_hash")
    @patch("samcli.lib.build.build_graph.BuildGraph._compare_hash_changes")
    def test_update_definition_hash_should_succeed(self, compare_hash_mock, write_hash_mock):
        compare_hash_mock.return_value = {"mock": "hash"}
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            current_function_build_definitions = build_graph.get_function_build_definitions()
            current_layer_build_definitions = build_graph.get_layer_build_definitions()

            build_graph.update_definition_hash()

            write_hash_mock.assert_called_with({"mock": "hash"}, {"mock": "hash"})
            self.assertEqual(current_function_build_definitions, build_graph.get_function_build_definitions())
            self.assertEqual(current_layer_build_definitions, build_graph.get_layer_build_definitions())

    def test_compare_hash_changes_should_succeed(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_definition = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            updated_definition = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                "new_value",
                "new_manifest_value",
                TestBuildGraph.ENV_VARS,
            )
            updated_definition.uuid = build_definition.uuid

            layer_definition = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            updated_layer = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.ARCHITECTURE_FIELD,
                "new_value",
                "new_manifest_value",
                TestBuildGraph.ENV_VARS,
            )
            updated_layer.uuid = layer_definition.uuid

            build_graph._function_build_definitions = [build_definition]
            build_graph._layer_build_definitions = [layer_definition]

            function_content = BuildGraph._compare_hash_changes(
                [updated_definition], build_graph._function_build_definitions
            )
            layer_content = BuildGraph._compare_hash_changes([updated_layer], build_graph._layer_build_definitions)
            self.assertEqual(function_content, {build_definition.uuid: ("new_value", "new_manifest_value")})
            self.assertEqual(layer_content, {layer_definition.uuid: ("new_value", "new_manifest_value")})

    @parameterized.expand(
        [
            ("manifest_hash", "manifest_hash", False),
            ("manifest_hash", "new_manifest_hash", True),
        ]
    )
    def test_compare_hash_changes_should_preserve_download_dependencies(
        self, old_manifest, new_manifest, download_dependencies
    ):
        updated_definition = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, X86_64, {}, "app.handler", manifest_hash=old_manifest
        )
        existing_definition = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, X86_64, {}, "app.handler", manifest_hash=new_manifest
        )
        BuildGraph._compare_hash_changes([updated_definition], [existing_definition])
        self.assertEqual(existing_definition.download_dependencies, download_dependencies)

    def test_write_source_hash_should_succeed(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_graph._write_source_hash(
                {TestBuildGraph.UUID: BuildHashingInformation("new_value", "new_manifest_value")},
                {TestBuildGraph.LAYER_UUID: BuildHashingInformation("new_value", "new_manifest_value")},
            )

            txt = build_graph_path.read_text()
            document = cast(Dict, tomlkit.loads(txt))

            self.assertEqual(
                document["function_build_definitions"][TestBuildGraph.UUID][SOURCE_HASH_FIELD], "new_value"
            )
            self.assertEqual(
                document["function_build_definitions"][TestBuildGraph.UUID][MANIFEST_HASH_FIELD], "new_manifest_value"
            )
            self.assertEqual(
                document["layer_build_definitions"][TestBuildGraph.LAYER_UUID][SOURCE_HASH_FIELD], "new_value"
            )
            self.assertEqual(
                document["layer_build_definitions"][TestBuildGraph.LAYER_UUID][MANIFEST_HASH_FIELD],
                "new_manifest_value",
            )

    def test_empty_get_function_build_definition_with_logical_id(self):
        build_graph = BuildGraph("build_dir")
        self.assertIsNone(build_graph.get_function_build_definition_with_full_path("function_logical_id"))

    def test_get_function_build_definition_with_logical_id(self):
        build_graph = BuildGraph("build_dir")
        logical_id = "function_logical_id"
        function = Mock()
        function.full_path = logical_id
        function_build_definition = Mock(functions=[function])
        build_graph._function_build_definitions = [function_build_definition]

        self.assertEqual(
            build_graph.get_function_build_definition_with_full_path(logical_id), function_build_definition
        )


class TestBuildDefinition(TestCase):
    def test_single_function_should_return_function_and_handler_name(self):
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, X86_64, {}, "handler", "source_hash", "manifest_hash", {"env_vars": "value"}
        )
        build_definition.add_function(generate_function())
        self.assertEqual(build_definition.get_handler_name(), "handler")
        self.assertEqual(build_definition.get_function_name(), "name")

    def test_no_function_should_raise_exception(self):
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, X86_64, {}, "handler", "source_hash", "manifest_hash", {"env_vars": "value"}
        )

        self.assertRaises(InvalidBuildGraphException, build_definition.get_handler_name)
        self.assertRaises(InvalidBuildGraphException, build_definition.get_function_name)

    def test_same_runtime_codeuri_metadata_should_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, {"key": "value"}, "handler", "source_hash", "manifest_hash"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, {"key": "value"}, "handler", "source_hash", "manifest_hash"
        )

        self.assertEqual(build_definition1, build_definition2)

    def test_skip_sam_related_metadata_should_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            ZIP,
            ARM64,
            {"key": "value", "SamResourceId": "resourceId1", "SamNormalized": True},
            "handler",
            "source_hash",
            "manifest_hash",
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            ZIP,
            ARM64,
            {"key": "value", "SamResourceId": "resourceId2", "SamNormalized": True},
            "handler",
            "source_hash",
            "manifest_hash",
        )

        self.assertEqual(build_definition1, build_definition2)

    def test_same_env_vars_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            ZIP,
            X86_64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value"},
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            ZIP,
            X86_64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value"},
        )

        self.assertEqual(build_definition1, build_definition2)

    @parameterized.expand(
        [
            (
                "runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
                "runtime",
                "codeuri",
                ({"key": "different_value"}),
                "source_hash",
            ),
            (
                "runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
                "different_runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
            ),
            (
                "runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
                "runtime",
                "different_codeuri",
                ({"key": "value"}),
                "source_hash",
            ),
            # custom build method with Makefile definition should always be identified as different
            (
                "runtime",
                "codeuri",
                ({"BuildMethod": "makefile"}),
                "source_hash",
                "runtime",
                "codeuri",
                ({"BuildMethod": "makefile"}),
                "source_hash",
            ),
        ]
    )
    def test_different_runtime_codeuri_metadata_should_not_reflect_as_same_object(
        self, runtime1, codeuri1, metadata1, source_hash_1, runtime2, codeuri2, metadata2, source_hash_2
    ):
        build_definition1 = FunctionBuildDefinition(runtime1, codeuri1, ZIP, ARM64, metadata1, source_hash_1)
        build_definition2 = FunctionBuildDefinition(runtime2, codeuri2, ZIP, ARM64, metadata2, source_hash_2)

        self.assertNotEqual(build_definition1, build_definition2)

    def test_different_architecture_should_not_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, X86_64, {"key": "value"}, "handler", "source_md5", {"env_vars": "value"}
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, {"key": "value"}, "handler", "source_md5", {"env_vars": "value"}
        )

        self.assertNotEqual(build_definition1, build_definition2)

    def test_different_env_vars_should_not_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            ZIP,
            ARM64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value1"},
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            ZIP,
            ARM64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value2"},
        )

        self.assertNotEqual(build_definition1, build_definition2)

    def test_euqality_with_another_object(self):
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, X86_64, None, "source_hash", "manifest_hash"
        )
        self.assertNotEqual(build_definition, {})

    def test_str_representation(self):
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, None, "handler", "source_hash", "manifest_hash"
        )
        self.assertEqual(
            str(build_definition),
            f"BuildDefinition(runtime, codeuri, Zip, source_hash, {build_definition.uuid}, {{}}, {{}}, arm64, [])",
        )

    def test_esbuild_definitions_equal_objects_independent_build_method(self):
        build_graph = BuildGraph("build/path")
        metadata = {"BuildMethod": "esbuild"}
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler-1"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, metadata, "app.handler", "source_hash", "manifest_hash"
        )
        function2 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler-2"
        )
        build_graph.put_function_build_definition(build_definition1, function1)
        build_graph.put_function_build_definition(build_definition2, function2)

        build_definitions = build_graph.get_function_build_definitions()

        self.assertNotEqual(build_definition1, build_definition2)
        self.assertEqual(len(build_definitions), 2)
        self.assertEqual(len(build_definition1.functions), 1)
        self.assertEqual(len(build_definition2.functions), 1)

    def test_independent_build_definitions_equal_objects_one_esbuild_build_method(self):
        build_graph = BuildGraph("build/path")
        metadata = {"BuildMethod": "esbuild"}
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler-1"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, {}, "handler", "source_hash", "manifest_hash"
        )
        function2 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata={}, handler="handler-2"
        )
        build_graph.put_function_build_definition(build_definition1, function1)
        build_graph.put_function_build_definition(build_definition2, function2)

        build_definitions = build_graph.get_function_build_definitions()

        self.assertNotEqual(build_definition1, build_definition2)
        self.assertEqual(len(build_definitions), 2)
        self.assertEqual(len(build_definition1.functions), 1)
        self.assertEqual(len(build_definition2.functions), 1)

    def test_two_esbuild_methods_same_handler(self):
        build_graph = BuildGraph("build/path")
        metadata = {"BuildMethod": "esbuild"}
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function2 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata={}, handler="handler"
        )
        build_graph.put_function_build_definition(build_definition1, function1)
        build_graph.put_function_build_definition(build_definition2, function2)

        build_definitions = build_graph.get_function_build_definitions()

        self.assertEqual(build_definition1, build_definition2)
        self.assertEqual(len(build_definitions), 1)
        self.assertEqual(len(build_definition1.functions), 2)

    @parameterized.expand([(True,), (False,)])
    @patch("samcli.lib.build.build_graph.is_experimental_enabled")
    def test_build_folder_with_multiple_functions(self, build_improvements_22_enabled, patched_is_experimental):
        patched_is_experimental.return_value = build_improvements_22_enabled
        build_graph = BuildGraph("build/path")
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", ZIP, ARM64, {}, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, handler="handler")
        function2 = generate_function(runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, handler="handler")
        build_graph.put_function_build_definition(build_definition, function1)
        build_graph.put_function_build_definition(build_definition, function2)

        if not build_improvements_22_enabled:
            self.assertEqual(
                build_definition.get_build_dir("build_dir"), build_definition.functions[0].get_build_dir("build_dir")
            )
        else:
            self.assertEqual(
                build_definition.get_build_dir("build_dir"),
                build_definition.functions[0].get_build_dir("build_dir") + "-Shared",
            )
