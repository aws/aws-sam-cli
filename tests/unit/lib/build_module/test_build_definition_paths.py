import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.lib.build.build_graph import (
    BuildGraph,
    FunctionBuildDefinition,
    get_build_definition_dir,
    is_valid_build_definition_uuid,
)
from samcli.lib.build.build_strategy import CachedBuildStrategy
from samcli.lib.build.exceptions import InvalidBuildGraphException
from samcli.lib.utils import osutils
from samcli.lib.utils.architecture import X86_64
from samcli.lib.utils.packagetype import ZIP

VALID_UUID = "3c1c254e-cd4b-4d94-8c74-7ab870b36063"
INVALID_KEY = "../../other"

BUILD_TOML_WITH_INVALID_KEYS = f"""
[function_build_definitions]
[function_build_definitions."{INVALID_KEY}"]
codeuri = "src"
runtime = "python3.12"
packagetype = "{ZIP}"
architecture = "{X86_64}"
handler = "app.handler"
source_hash = "stale"
functions = ["Fn"]

[function_build_definitions.{VALID_UUID}]
codeuri = "other"
runtime = "python3.12"
packagetype = "{ZIP}"
architecture = "{X86_64}"
handler = "app.handler"
functions = ["Other"]

[layer_build_definitions]
[layer_build_definitions."../layer"]
layer_name = "Layer"
codeuri = "layer"
build_method = "python3.12"
compatible_runtimes = ["python3.12"]
architecture = "{X86_64}"
layer = "Layer"
"""


class TestIsValidBuildDefinitionUuid(TestCase):
    @parameterized.expand([(VALID_UUID,), ("0f6f7e2a-9a3b-4c1d-8e5f-1a2b3c4d5e6f",)])
    def test_canonical_uuid_is_valid(self, value):
        self.assertTrue(is_valid_build_definition_uuid(value))

    @parameterized.expand(
        [
            (INVALID_KEY,),
            ("../layer",),
            ("/absolute/path",),
            ("",),
            (".",),
            ("..",),
            (VALID_UUID.upper(),),
            ("{" + VALID_UUID + "}",),
            (VALID_UUID.replace("-", ""),),
            (VALID_UUID + "/..",),
            ("7dnc257e-cd4b-4d94-8c74-7ab870b3abc3",),
            (None,),
            (123,),
        ]
    )
    def test_anything_else_is_invalid(self, value):
        self.assertFalse(is_valid_build_definition_uuid(value))


class TestGetBuildDefinitionDir(TestCase):
    def test_returns_child_of_parent(self):
        with osutils.mkdir_temp() as parent:
            self.assertEqual(get_build_definition_dir(parent, VALID_UUID), os.path.join(parent, VALID_UUID))

    def test_rejects_invalid_uuid(self):
        with osutils.mkdir_temp() as parent:
            with self.assertRaises(InvalidBuildGraphException):
                get_build_definition_dir(parent, INVALID_KEY)

    def test_rejects_symlink_outside_parent(self):
        with osutils.mkdir_temp() as temp_dir:
            parent = Path(temp_dir, "cache")
            parent.mkdir()
            outside = Path(temp_dir, "outside")
            outside.mkdir()
            Path(parent, VALID_UUID).symlink_to(outside, target_is_directory=True)

            with self.assertRaises(InvalidBuildGraphException):
                get_build_definition_dir(str(parent), VALID_UUID)

    def test_dependencies_dir_rejects_invalid_uuid(self):
        definition = FunctionBuildDefinition("python3.12", "src", None, ZIP, X86_64, {}, "app.handler")
        definition.uuid = INVALID_KEY
        with self.assertRaises(InvalidBuildGraphException):
            _ = definition.dependencies_dir


class TestBuildGraphIgnoresInvalidKeys(TestCase):
    def test_invalid_keys_are_dropped_and_valid_ones_kept(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            Path(build_dir.parent, "build.toml").write_text(BUILD_TOML_WITH_INVALID_KEYS)

            build_graph = BuildGraph(str(build_dir))

            function_definitions = build_graph.get_function_build_definitions()
            self.assertEqual([d.uuid for d in function_definitions], [VALID_UUID])
            self.assertEqual(build_graph.get_layer_build_definitions(), ())

    def test_matching_function_gets_new_uuid(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            Path(build_dir.parent, "build.toml").write_text(BUILD_TOML_WITH_INVALID_KEYS)
            build_graph = BuildGraph(str(build_dir))

            new_definition = FunctionBuildDefinition("python3.12", "src", None, ZIP, X86_64, {}, "app.handler")
            function = Mock()
            function.full_path = "Fn"
            build_graph.put_function_build_definition(new_definition, function)

            uuids = [d.uuid for d in build_graph.get_function_build_definitions()]
            self.assertNotIn(INVALID_KEY, uuids)
            self.assertTrue(all(is_valid_build_definition_uuid(u) for u in uuids))


class TestCachedBuildStrategyInvalidUuid(TestCase):
    def test_invalid_uuid_is_rejected_before_build(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)
            Path(temp_base_dir, "src").mkdir()

            other = Path(temp_base_dir, "other")
            other.mkdir()
            Path(other, "file").write_text("content")

            definition = FunctionBuildDefinition("python3.12", "src", None, ZIP, X86_64, {}, "app.handler")
            definition.uuid = "../../other"
            delegate = Mock()
            delegate.build_single_function_definition.return_value = {"Fn": str(build_dir)}
            strategy = CachedBuildStrategy(
                BuildGraph(str(build_dir)), delegate, temp_base_dir, str(build_dir), str(cache_dir)
            )

            with self.assertRaises(InvalidBuildGraphException):
                strategy.build_single_function_definition(definition)

            delegate.build_single_function_definition.assert_not_called()
            self.assertEqual(Path(other, "file").read_text(), "content")
