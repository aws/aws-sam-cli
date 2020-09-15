from unittest import TestCase
from uuid import uuid4

import tomlkit

from samcli.lib.build.build_graph import BuildDefinition, _build_definition_to_toml_table, CODE_URI_FIELD, \
    RUNTIME_FIELD, METADATA_FIELD, FUNCTIONS_FIELD, _toml_table_to_build_definition
from samcli.lib.providers.provider import Function


class TestConversionFunctions(TestCase):

    def test_build_definition_to_toml_table(self):
        build_definition = BuildDefinition("runtime", "codeuri", {"key": "value"})
        build_definition.add_function(Function("name", "function_name", "runtime", "memory", "timeout", "handler",
                                               "codeuri", "environment", "rolearn", "layers", "events", "metadata"))

        toml_table = _build_definition_to_toml_table(build_definition)

        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[RUNTIME_FIELD], build_definition.runtime)
        self.assertEqual(toml_table[METADATA_FIELD], build_definition.metadata)
        self.assertEqual(toml_table[FUNCTIONS_FIELD], [f.functionname for f in build_definition.functions])

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
    # will be updated within next task
    pass

class TestBuildDefinition(TestCase):
    # will be updated within next task
    pass
