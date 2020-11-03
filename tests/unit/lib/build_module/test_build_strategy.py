from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, call, ANY

from samcli.commands.build.exceptions import MissingBuildMethodException
from samcli.lib.build.build_graph import BuildGraph, FunctionBuildDefinition, LayerBuildDefinition
from samcli.lib.build.build_strategy import BuildStrategy, DefaultBuildStrategy, CachedBuildStrategy
from samcli.lib.utils import osutils
from pathlib import Path


@patch("samcli.lib.build.build_graph.BuildGraph._write")
@patch("samcli.lib.build.build_graph.BuildGraph._read")
class BuildStrategyBaseTest(TestCase):
    def setUp(self):
        # create a build graph with 2 function definitions and 2 layer definitions
        self.build_graph = BuildGraph("build_dir")

        self.function1_1 = Mock()
        self.function1_2 = Mock()
        self.function2 = Mock()

        self.function_build_definition1 = FunctionBuildDefinition("runtime", "codeuri", {})
        self.function_build_definition1.functions = [self.function1_1, self.function1_2]
        self.function_build_definition2 = FunctionBuildDefinition("runtime2", "codeuri", {})
        self.function_build_definition1.functions = [self.function2]
        self.build_graph.put_function_build_definition(self.function_build_definition1, Mock())
        self.build_graph.put_function_build_definition(self.function_build_definition2, Mock())

        self.layer_build_definition1 = LayerBuildDefinition("layer1", "codeuri", "build_method", [])
        self.layer_build_definition2 = LayerBuildDefinition("layer2", "codeuri", "build_method", [])
        self.build_graph.put_layer_build_definition(self.layer_build_definition1, Mock())
        self.build_graph.put_layer_build_definition(self.layer_build_definition2, Mock())


class BuildStrategyTest(BuildStrategyBaseTest):
    def test_build_functions_layers(self):
        build_strategy = BuildStrategy(self.build_graph)

        self.assertEqual(build_strategy.build(), {})

    def test_build_functions_layers_mock(self):
        mock_build_strategy = BuildStrategy(self.build_graph)
        given_build_functions_result = {"function1": "build_dir_1"}
        given_build_layers_result = {"layer1": "layer_dir_1"}

        mock_build_strategy._build_functions = Mock(return_value=given_build_functions_result)
        mock_build_strategy._build_layers = Mock(return_value=given_build_layers_result)
        build_result = mock_build_strategy.build()

        expected_result = {}
        expected_result.update(given_build_functions_result)
        expected_result.update(given_build_layers_result)
        self.assertEqual(build_result, expected_result)

        mock_build_strategy._build_functions.assert_called_once_with(self.build_graph)
        mock_build_strategy._build_layers.assert_called_once_with(self.build_graph)

    def test_build_single_function_layer(self):
        mock_build_strategy = BuildStrategy(self.build_graph)
        given_build_functions_result = [{"function1": "build_dir_1"}, {"function2": "build_dir_2"}]
        given_build_layers_result = [{"layer1": "layer_dir_1"}, {"layer2": "layer_dir_2"}]

        mock_build_strategy.build_single_function_definition = Mock(side_effect=given_build_functions_result)
        mock_build_strategy.build_single_layer_definition = Mock(side_effect=given_build_layers_result)
        build_result = mock_build_strategy.build()

        expected_result = {}
        for function_result in given_build_functions_result:
            expected_result.update(function_result)
        for layer_result in given_build_layers_result:
            expected_result.update(layer_result)

        self.assertEqual(build_result, expected_result)

        # assert individual functions builds have been called
        mock_build_strategy.build_single_function_definition.assert_has_calls(
            [
                call(self.function_build_definition1),
                call(self.function_build_definition2),
            ]
        )

        # assert individual layer builds have been called
        mock_build_strategy.build_single_layer_definition.assert_has_calls(
            [
                call(self.layer_build_definition1),
                call(self.layer_build_definition2),
            ]
        )


@patch("samcli.lib.build.build_strategy.pathlib.Path")
@patch("samcli.lib.build.build_strategy.osutils.copytree")
class DefaultBuildStrategyTest(BuildStrategyBaseTest):
    def test_layer_build_should_fail_when_no_build_method_is_provided(self, mock_copy_tree, mock_path):
        given_layer = Mock()
        given_layer.build_method = None
        layer_build_definition = LayerBuildDefinition("layer1", "codeuri", "build_method", [])
        layer_build_definition.layer = given_layer

        build_graph = Mock(spec=BuildGraph)
        build_graph.get_layer_build_definitions.return_value = [layer_build_definition]
        build_graph.get_function_build_definitions.return_value = []
        default_build_strategy = DefaultBuildStrategy(build_graph, "build_dir", Mock(), Mock())

        self.assertRaises(MissingBuildMethodException, default_build_strategy.build)

    def test_build_layers_and_functions(self, mock_copy_tree, mock_path):
        given_build_function = Mock()
        given_build_layer = Mock()
        given_build_dir = "build_dir"
        default_build_strategy = DefaultBuildStrategy(
            self.build_graph, given_build_dir, given_build_function, given_build_layer
        )

        default_build_strategy.build()

        # assert that build function has been called
        given_build_function.assert_has_calls(
            [
                call(
                    self.function_build_definition1.get_function_name(),
                    self.function_build_definition1.codeuri,
                    self.function_build_definition1.runtime,
                    self.function_build_definition1.get_handler_name(),
                    ANY,
                    self.function_build_definition1.metadata,
                ),
                call(
                    self.function_build_definition2.get_function_name(),
                    self.function_build_definition2.codeuri,
                    self.function_build_definition2.runtime,
                    self.function_build_definition2.get_handler_name(),
                    ANY,
                    self.function_build_definition2.metadata,
                ),
            ]
        )

        # assert that layer build function has been called
        given_build_layer.assert_has_calls(
            [
                call(
                    self.layer_build_definition1.layer.name,
                    self.layer_build_definition1.layer.codeuri,
                    self.layer_build_definition1.layer.build_method,
                    self.layer_build_definition1.layer.compatible_runtimes,
                ),
                call(
                    self.layer_build_definition2.layer.name,
                    self.layer_build_definition2.layer.codeuri,
                    self.layer_build_definition2.layer.build_method,
                    self.layer_build_definition2.layer.compatible_runtimes,
                ),
            ]
        )

        # assert that mock path has been called
        mock_path.assert_has_calls(
            [
                call(given_build_dir, self.function_build_definition1.get_function_name()),
                call(given_build_dir, self.function_build_definition2.get_function_name()),
            ],
            any_order=True,
        )

        # assert that function1_2 artifacts have been copied from already built function1_1
        mock_copy_tree.assert_called_with(
            str(mock_path(given_build_dir, self.function_build_definition1.get_function_name())),
            str(mock_path(given_build_dir, self.function1_2.name)),
        )


class CachedBuildStrategyTest(BuildStrategyBaseTest):
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

    @patch("samcli.lib.build.build_strategy.pathlib.Path")
    @patch("samcli.lib.build.build_strategy.osutils.copytree")
    @patch("samcli.lib.build.build_strategy.shutil.rmtree")
    @patch("samcli.lib.build.build_strategy.DefaultBuildStrategy.build_single_function_definition")
    @patch("samcli.lib.build.build_strategy.DefaultBuildStrategy.build_single_layer_definition")
    def test_build_call(self, mock_layer_build, mock_function_build, mock_rmtree, mock_copy_tree, mock_path):
        given_build_function = Mock()
        given_build_layer = Mock()
        given_build_dir = "build_dir"
        default_build_strategy = DefaultBuildStrategy(
            self.build_graph, given_build_dir, given_build_function, given_build_layer
        )
        cache_build_strategy = CachedBuildStrategy(
            self.build_graph, default_build_strategy, "base_dir", given_build_dir, "cache_dir", True
        )
        cache_build_strategy.build()
        mock_function_build.assert_called()
        mock_layer_build.assert_called()

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
                build_graph, DefaultBuildStrategy, temp_base_dir, build_dir, cache_dir, True
            )
            func1 = Mock()
            func1.name = "func1_name"
            func2 = Mock()
            func2.name = "func2_name"
            build_definition = build_graph.get_function_build_definitions()[0]
            layer_definition = build_graph.get_layer_build_definitions()[0]
            build_graph.put_function_build_definition(build_definition, func1)
            build_graph.put_function_build_definition(build_definition, func2)
            layer = Mock()
            layer.name = "layer_name"
            build_graph.put_layer_build_definition(layer_definition, layer)
            cached_build_strategy.build_single_function_definition(build_definition)
            cached_build_strategy.build_single_layer_definition(layer_definition)
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
                build_graph, DefaultBuildStrategy, temp_base_dir, build_dir, cache_dir, True
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

            cached_build_strategy = CachedBuildStrategy(build_graph, Mock(), temp_base_dir, build_dir, cache_dir, True)
            cached_build_strategy._clean_redundant_cached()
            self.assertTrue(not redundant_cache_folder.exists())
