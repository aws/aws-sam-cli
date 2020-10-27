from unittest import TestCase
from unittest.mock import Mock, patch
from pathlib import Path

from samcli.lib.build.build_graph import BuildGraph
from samcli.lib.build.build_strategy import CachedBuildStrategy, DefaultBuildStrategy
from samcli.lib.utils import osutils


class BuildStrategyTest(TestCase):
    pass


class DefaultBuildStrategyTest(TestCase):
    pass


class CachedBuildStrategyTest(TestCase):
    CODEURI = "hello_world_python/"
    RUNTIME = "python3.8"
    FUNCTION_UUID = "3c1c254e-cd4b-4d94-8c74-7ab870b36063"
    SOURCE_MD5 = "cae49aa393d669e850bd49869905099d"
    LAYER_UUID = "761ce752-d1c8-4e07-86a0-f64778cdd108"
    LAYER_METHOD = "nodejs12.x"

    BUILD_GRAPH_CONTENTS = f"""
    [function_build_definitions]
    [function_build_definitions.{FUNCTION_UUID}]
    codeuri = "{CODEURI}"
    runtime = "{RUNTIME}"
    source_md5 = "{SOURCE_MD5}"
    functions = ["HelloWorldPython", "HelloWorldPython2"]

    [layer_build_definitions]
    [layer_build_definitions.{LAYER_UUID}]
    layer_name = "SumLayer"
    codeuri = "sum_layer/"
    build_method = "nodejs12.x"
    compatible_runtimes = ["nodejs12.x"]
    source_md5 = "{SOURCE_MD5}"
    layer = "SumLayer"
    """

    @patch("samcli.lib.build.build_strategy.osutils.copytree")
    @patch("samcli.lib.build.build_strategy.pathlib.Path.exists")
    @patch("samcli.lib.build.build_strategy.dir_checksum")
    def test_if_cached_valid_when_build_single_function_definition(self, dir_checksum_mock, exists_mock, copytree_mock):
        pass
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)

            exists_mock.return_value = True
            dir_checksum_mock.return_value = CachedBuildStrategyTest.SOURCE_MD5

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(CachedBuildStrategyTest.BUILD_GRAPH_CONTENTS)
            build_graph = BuildGraph(str(build_dir))
            cached_build_strategy = CachedBuildStrategy(
                build_graph, DefaultBuildStrategy, temp_base_dir, build_dir, cache_dir
            )
            func1 = Mock()
            func1.name = "func1_name"
            func2 = Mock()
            func2.name = "func2_name"
            build_graph.put_function_build_definition(build_graph.get_function_build_definitions()[0], func1)
            build_graph.put_function_build_definition(build_graph.get_function_build_definitions()[0], func2)
            layer = Mock()
            layer.name = "layer_name"
            build_graph.put_layer_build_definition(build_graph.get_layer_build_definitions()[0], layer)
            cached_build_strategy.build_single_function_definition(build_graph.get_function_build_definitions()[0])
            cached_build_strategy.build_single_layer_definition(build_graph.get_layer_build_definitions()[0])
            self.assertEqual(copytree_mock.call_count, 3)

    @patch("samcli.lib.build.build_strategy.osutils.copytree")
    @patch("samcli.lib.build.build_strategy.DefaultBuildStrategy.build_single_function_definition")
    @patch("samcli.lib.build.build_strategy.DefaultBuildStrategy.build_single_layer_definition")
    def test_if_cached_invalid_with_no_cached_folder(self, build_layer_mock, build_function_mock, copytree_mock):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)

            build_function_mock.return_value = {"HelloWorldPython": "artifact1", "HelloWorldPython2": "artifact2"}
            build_layer_mock.return_value = {"SumLayer": "artifact3"}

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(CachedBuildStrategyTest.BUILD_GRAPH_CONTENTS)
            build_graph = BuildGraph(str(build_dir))
            cached_build_strategy = CachedBuildStrategy(
                build_graph, DefaultBuildStrategy, temp_base_dir, build_dir, cache_dir
            )
            cached_build_strategy.build_single_function_definition(build_graph.get_function_build_definitions()[0])
            cached_build_strategy.build_single_layer_definition(build_graph.get_layer_build_definitions()[0])
            build_function_mock.assert_called_once()
            build_layer_mock.assert_called_once()
            self.assertEqual(copytree_mock.call_count, 2)

    def test_redundant_cached_should_be_clean(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            build_graph = BuildGraph(str(build_dir.resolve()))
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)
            redundant_cache_folder = Path(cache_dir, "redundant")
            redundant_cache_folder.mkdir(parents=True)

            cached_build_strategy = CachedBuildStrategy(build_graph, Mock(), temp_base_dir, build_dir, cache_dir)
            cached_build_strategy._clean_redundant_cached()
            self.assertTrue(not redundant_cache_folder.exists())
