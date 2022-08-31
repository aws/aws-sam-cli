import itertools
from copy import deepcopy
from typing import List, Dict
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, call, ANY

from parameterized import parameterized

from samcli.lib.utils.architecture import X86_64, ARM64
from samcli.lib.build.exceptions import MissingBuildMethodException
from samcli.lib.build.build_graph import BuildGraph, FunctionBuildDefinition, LayerBuildDefinition
from samcli.lib.build.build_strategy import (
    ParallelBuildStrategy,
    BuildStrategy,
    DefaultBuildStrategy,
    CachedBuildStrategy,
    CachedOrIncrementalBuildStrategyWrapper,
    IncrementalBuildStrategy,
)
from samcli.lib.utils import osutils
from pathlib import Path

from samcli.lib.utils.packagetype import ZIP, IMAGE


@patch("samcli.lib.build.build_graph.BuildGraph._write")
@patch("samcli.lib.build.build_graph.BuildGraph._read")
class BuildStrategyBaseTest(TestCase):
    def setUp(self):
        # create a build graph with 2 function definitions and 2 layer definitions
        self.build_graph = BuildGraph("build_dir")

        self.function1_1 = Mock()
        self.function1_1.inlinecode = None
        self.function1_1.get_build_dir = Mock()
        self.function1_1.full_path = "function1_1"
        self.function1_2 = Mock()
        self.function1_2.inlinecode = None
        self.function1_2.get_build_dir = Mock()
        self.function1_2.full_path = "function1_2"
        self.function2 = Mock()
        self.function2.inlinecode = None
        self.function2.get_build_dir = Mock()
        self.function2.full_path = "function2"

        self.function_build_definition1 = FunctionBuildDefinition("runtime", "codeuri", ZIP, X86_64, {}, "handler")
        self.function_build_definition2 = FunctionBuildDefinition("runtime2", "codeuri", ZIP, X86_64, {}, "handler")

        self.function_build_definition1.add_function(self.function1_1)
        self.function_build_definition1.add_function(self.function1_2)
        self.function_build_definition2.add_function(self.function2)

        self.build_graph.put_function_build_definition(self.function_build_definition1, self.function1_1)
        self.build_graph.put_function_build_definition(self.function_build_definition1, self.function1_2)
        self.build_graph.put_function_build_definition(self.function_build_definition2, self.function2)

        self.layer1 = Mock()
        self.layer2 = Mock()

        self.layer_build_definition1 = LayerBuildDefinition("layer1", "codeuri", "build_method", [], X86_64)
        self.layer_build_definition2 = LayerBuildDefinition("layer2", "codeuri", "build_method", [], X86_64)
        self.build_graph.put_layer_build_definition(self.layer_build_definition1, self.layer1)
        self.build_graph.put_layer_build_definition(self.layer_build_definition2, self.layer2)


class _TestBuildStrategy(BuildStrategy):
    def build_single_function_definition(self, build_definition):
        return {}

    def build_single_layer_definition(self, layer_definition):
        return {}


class BuildStrategyTest(BuildStrategyBaseTest):
    def test_build_functions_layers(self):
        build_strategy = _TestBuildStrategy(self.build_graph)

        self.assertEqual(build_strategy.build(), {})

    def test_build_functions_layers_mock(self):
        mock_build_strategy = _TestBuildStrategy(self.build_graph)
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
        mock_build_strategy = _TestBuildStrategy(self.build_graph)
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


@patch("samcli.lib.build.build_strategy.osutils.copytree")
class DefaultBuildStrategyTest(BuildStrategyBaseTest):
    def test_layer_build_should_fail_when_no_build_method_is_provided(self, mock_copy_tree):
        given_layer = Mock()
        given_layer.build_method = None
        layer_build_definition = LayerBuildDefinition("layer1", "codeuri", "build_method", [], X86_64)
        layer_build_definition.layer = given_layer

        build_graph = Mock(spec=BuildGraph)
        build_graph.get_layer_build_definitions.return_value = [layer_build_definition]
        build_graph.get_function_build_definitions.return_value = []
        mock_function = Mock()
        mock_function.inlinecode = None
        default_build_strategy = DefaultBuildStrategy(build_graph, "build_dir", mock_function, Mock())

        self.assertRaises(MissingBuildMethodException, default_build_strategy.build)

    def test_build_layers_and_functions(self, mock_copy_tree):
        given_build_function = Mock()
        given_build_function.inlinecode = None
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
                    ZIP,
                    self.function_build_definition1.runtime,
                    self.function_build_definition1.architecture,
                    self.function_build_definition1.get_handler_name(),
                    self.function_build_definition1.get_build_dir(given_build_dir),
                    self.function_build_definition1.metadata,
                    self.function_build_definition1.env_vars,
                    None,
                    True,
                ),
                call(
                    self.function_build_definition2.get_function_name(),
                    self.function_build_definition2.codeuri,
                    ZIP,
                    self.function_build_definition2.runtime,
                    self.function_build_definition2.architecture,
                    self.function_build_definition2.get_handler_name(),
                    self.function_build_definition2.get_build_dir(given_build_dir),
                    self.function_build_definition2.metadata,
                    self.function_build_definition2.env_vars,
                    None,
                    True,
                ),
            ]
        )

        # assert that layer build function has been called
        given_build_layer.assert_has_calls(
            [
                call(
                    self.layer1.name,
                    self.layer1.codeuri,
                    self.layer1.build_method,
                    self.layer1.compatible_runtimes,
                    self.layer1.build_architecture,
                    self.layer1.get_build_dir(given_build_dir),
                    self.layer_build_definition1.env_vars,
                    None,
                    True,
                    self.layer1.metadata,
                ),
                call(
                    self.layer2.name,
                    self.layer2.codeuri,
                    self.layer2.build_method,
                    self.layer2.compatible_runtimes,
                    self.layer2.build_architecture,
                    self.layer2.get_build_dir(given_build_dir),
                    self.layer_build_definition2.env_vars,
                    None,
                    True,
                    self.layer2.metadata,
                ),
            ]
        )
        # previously we also assert artifact dir here.
        # since artifact dir is now determined in samcli/lib/providers/provider.py
        # we will not do assertion here

        # # assert that function1_2 artifacts have been copied from already built function1_1
        mock_copy_tree.assert_called_with(
            self.function_build_definition1.get_build_dir(given_build_dir),
            self.function1_2.get_build_dir(given_build_dir),
        )

    @patch("samcli.lib.build.build_strategy.is_experimental_enabled")
    def test_dedup_build_functions_with_symlink(self, patched_is_experimental, mock_copy_tree):
        patched_is_experimental.return_value = True
        given_build_function = Mock()
        given_build_function.inlinecode = None
        given_build_layer = Mock()
        given_build_dir = "build_dir"
        default_build_strategy = DefaultBuildStrategy(
            self.build_graph, given_build_dir, given_build_function, given_build_layer
        )

        build_result = default_build_strategy.build()
        # with 22 build improvements, functions with same build definitions should point to same artifact folder
        self.assertEqual(
            build_result.get(self.function_build_definition1.functions[0].full_path),
            build_result.get(self.function_build_definition1.functions[1].full_path),
        )

        # assert that copy operation is not called
        mock_copy_tree.assert_not_called()

    def test_build_single_function_definition_image_functions_with_same_metadata(self, mock_copy_tree):
        given_build_function = Mock()
        built_image = Mock()
        given_build_function.return_value = built_image
        given_build_layer = Mock()
        given_build_dir = "build_dir"
        default_build_strategy = DefaultBuildStrategy(
            self.build_graph, given_build_dir, given_build_function, given_build_layer
        )

        function1 = Mock()
        function1.name = "Function"
        function1.full_path = "Function"
        function1.packagetype = IMAGE
        function2 = Mock()
        function2.name = "Function2"
        function2.full_path = "Function2"
        function2.packagetype = IMAGE
        build_definition = FunctionBuildDefinition(
            "3.7", "codeuri", IMAGE, X86_64, {}, "handler", env_vars={"FOO": "BAR"}
        )
        # since they have the same metadata, they are put into the same build_definition.
        build_definition.functions = [function1, function2]

        with patch("samcli.lib.build.build_strategy.deepcopy", wraps=deepcopy) as patched_deepcopy:
            result = default_build_strategy.build_single_function_definition(build_definition)

            patched_deepcopy.assert_called_with(build_definition.env_vars)

        # both of the function name should show up in results
        self.assertEqual(result, {"Function": built_image, "Function2": built_image})


class CachedBuildStrategyTest(BuildStrategyBaseTest):
    CODEURI = "hello_world_python/"
    RUNTIME = "python3.8"
    FUNCTION_UUID = "3c1c254e-cd4b-4d94-8c74-7ab870b36063"
    SOURCE_HASH = "cae49aa393d669e850bd49869905099d"
    LAYER_UUID = "761ce752-d1c8-4e07-86a0-f64778cdd108"
    LAYER_METHOD = "nodejs12.x"

    BUILD_GRAPH_CONTENTS = f"""
    [function_build_definitions]
    [function_build_definitions.{FUNCTION_UUID}]
    codeuri = "{CODEURI}"
    packagetype = "{ZIP}"
    runtime = "{RUNTIME}"
    source_hash = "{SOURCE_HASH}"
    functions = ["HelloWorldPython", "HelloWorld2Python"]

    [layer_build_definitions]
    [layer_build_definitions.{LAYER_UUID}]
    layer_name = "SumLayer"
    codeuri = "sum_layer/"
    build_method = "nodejs12.x"
    compatible_runtimes = ["nodejs12.x"]
    source_hash = "{SOURCE_HASH}"
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
            self.build_graph, default_build_strategy, "base_dir", given_build_dir, "cache_dir"
        )
        cache_build_strategy.build()
        mock_function_build.assert_called()
        mock_layer_build.assert_called()

    @patch("samcli.lib.build.build_strategy.osutils.copytree")
    @patch("samcli.lib.build.build_strategy.pathlib.Path.exists")
    @patch("samcli.lib.build.build_strategy.dir_checksum")
    def test_if_cached_valid_when_build_single_function_definition(self, dir_checksum_mock, exists_mock, copytree_mock):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)

            exists_mock.return_value = True
            dir_checksum_mock.return_value = CachedBuildStrategyTest.SOURCE_HASH

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(CachedBuildStrategyTest.BUILD_GRAPH_CONTENTS)
            build_graph = BuildGraph(str(build_dir))
            cached_build_strategy = CachedBuildStrategy(
                build_graph, DefaultBuildStrategy, temp_base_dir, build_dir, cache_dir
            )
            func1 = Mock()
            func1.name = "func1_name"
            func1.full_path = "func1_full_path"
            func1.inlinecode = None
            func2 = Mock()
            func2.name = "func2_name"
            func2.full_path = "func2_full_path"
            func2.inlinecode = None
            build_definition = build_graph.get_function_build_definitions()[0]
            layer_definition = build_graph.get_layer_build_definitions()[0]
            build_graph.put_function_build_definition(build_definition, func1)
            build_graph.put_function_build_definition(build_definition, func2)
            layer = Mock()
            layer.name = "layer_name"
            layer.full_path = "layer_full_path"
            build_graph.put_layer_build_definition(layer_definition, layer)
            cached_build_strategy.build_single_function_definition(build_definition)
            cached_build_strategy.build_single_layer_definition(layer_definition)
            self.assertEqual(copytree_mock.call_count, 3)

    @parameterized.expand([(True,), (False,)])
    @patch("samcli.lib.build.build_strategy.osutils.copytree")
    @patch("samcli.lib.build.build_strategy.pathlib.Path.exists")
    @patch("samcli.lib.build.build_strategy.dir_checksum")
    @patch("samcli.lib.utils.osutils.os")
    @patch("samcli.lib.build.build_strategy.is_experimental_enabled")
    def test_if_cached_valid_when_build_single_function_definition_with_build_improvements_22(
        self, should_raise_os_error, patch_is_experimental, patch_os, dir_checksum_mock, exists_mock, copytree_mock
    ):
        patch_is_experimental.return_value = True
        if should_raise_os_error:
            patch_os.symlink.side_effect = OSError()
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)

            exists_mock.return_value = True
            dir_checksum_mock.return_value = CachedBuildStrategyTest.SOURCE_HASH

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(CachedBuildStrategyTest.BUILD_GRAPH_CONTENTS)
            build_graph = BuildGraph(str(build_dir))
            cached_build_strategy = CachedBuildStrategy(
                build_graph, DefaultBuildStrategy, temp_base_dir, build_dir, cache_dir
            )
            func1 = Mock()
            func1.name = "func1_name"
            func1.full_path = "func1_full_path"
            func1.inlinecode = None
            func1.get_build_dir.return_value = "func1/build/dir"
            func2 = Mock()
            func2.name = "func2_name"
            func2.full_path = "func2_full_path"
            func2.inlinecode = None
            build_definition = build_graph.get_function_build_definitions()[0]
            layer_definition = build_graph.get_layer_build_definitions()[0]
            build_graph.put_function_build_definition(build_definition, func1)
            build_graph.put_function_build_definition(build_definition, func2)
            layer = Mock()
            layer.name = "layer_name"
            layer.full_path = "layer_full_path"
            layer.get_build_dir.return_value = "layer/build/dir"
            build_graph.put_layer_build_definition(layer_definition, layer)
            cached_build_strategy.build_single_function_definition(build_definition)
            cached_build_strategy.build_single_layer_definition(layer_definition)

            if should_raise_os_error:
                copytree_mock.assert_has_calls(
                    [
                        call(
                            str(cache_dir.joinpath(build_graph.get_function_build_definitions()[0].uuid)),
                            build_graph.get_function_build_definitions()[0].functions[0].get_build_dir(build_dir),
                        ),
                        call(
                            str(cache_dir.joinpath(build_graph.get_layer_build_definitions()[0].uuid)),
                            build_graph.get_layer_build_definitions()[0].layer.get_build_dir(build_dir),
                        ),
                    ]
                )
            else:
                copytree_mock.assert_not_called()
                patch_os.symlink.assert_has_calls(
                    [
                        call(
                            cache_dir.joinpath(build_graph.get_function_build_definitions()[0].uuid),
                            Path(
                                build_graph.get_function_build_definitions()[0].functions[0].get_build_dir(build_dir)
                            ).absolute(),
                        ),
                        call(
                            cache_dir.joinpath(build_graph.get_layer_build_definitions()[0].uuid),
                            Path(
                                build_graph.get_layer_build_definitions()[0].layer.get_build_dir(build_dir)
                            ).absolute(),
                        ),
                    ]
                )

    @patch("samcli.lib.build.build_strategy.osutils.copytree")
    @patch("samcli.lib.build.build_strategy.DefaultBuildStrategy.build_single_function_definition")
    @patch("samcli.lib.build.build_strategy.DefaultBuildStrategy.build_single_layer_definition")
    def test_if_cached_invalid_with_no_cached_folder(self, build_layer_mock, build_function_mock, copytree_mock):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)

            build_function_mock.return_value = {"HelloWorldPython": "artifact1", "HelloWorld2Python": "artifact2"}
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


class ParallelBuildStrategyTest(BuildStrategyBaseTest):
    @patch("samcli.lib.build.build_strategy.AsyncContext")
    def test_given_async_context_should_call_expected_methods(self, patched_async_context):
        delegate_build_strategy = MagicMock(wraps=_TestBuildStrategy(self.build_graph))
        parallel_build_strategy = ParallelBuildStrategy(self.build_graph, delegate_build_strategy)

        mock_layer_async_context = Mock()
        mock_function_async_context = Mock()
        patched_async_context.side_effect = [mock_layer_async_context, mock_function_async_context]

        layer_build_results: List[Dict[str, str]] = [
            {"layer1": "layer_location1"},
            {"layer2": "layer_location2"},
        ]
        function_build_results: List[Dict[str, str]] = [
            {"function1": "function_location1"},
            {"function2": "function_location2"},
        ]
        mock_layer_async_context.run_async.return_value = layer_build_results
        mock_function_async_context.run_async.return_value = function_build_results

        results = parallel_build_strategy.build()

        expected_results = {}
        for given_build_result in layer_build_results + function_build_results:
            expected_results.update(given_build_result)
        self.assertEqual(results, expected_results)

        # assert that result has collected
        mock_layer_async_context.run_async.assert_has_calls([call()])
        mock_function_async_context.run_async.assert_has_calls([call()])

        # assert that delegated function calls have been registered in async context
        mock_layer_async_context.add_async_task.assert_has_calls(
            [
                call(parallel_build_strategy.build_single_layer_definition, self.layer_build_definition1),
                call(parallel_build_strategy.build_single_layer_definition, self.layer_build_definition2),
            ]
        )
        mock_function_async_context.add_async_task.assert_has_calls(
            [
                call(parallel_build_strategy.build_single_function_definition, self.function_build_definition1),
                call(parallel_build_strategy.build_single_function_definition, self.function_build_definition2),
            ]
        )

    def test_given_delegate_strategy_it_should_call_delegated_build_methods(self):
        # create a mock delegate build strategy
        delegate_build_strategy = MagicMock(wraps=_TestBuildStrategy(self.build_graph))
        delegate_build_strategy.build_single_function_definition.return_value = {
            "function1": "build_location1",
            "function2": "build_location2",
        }
        delegate_build_strategy.build_single_layer_definition.return_value = {
            "layer1": "build_location1",
            "layer2": "build_location2",
        }

        # create expected results
        expected_result = {}
        expected_result.update(delegate_build_strategy.build_single_function_definition.return_value)
        expected_result.update(delegate_build_strategy.build_single_layer_definition.return_value)

        # create build strategy with delegate
        parallel_build_strategy = ParallelBuildStrategy(self.build_graph, delegate_build_strategy)
        result = parallel_build_strategy.build()

        self.assertEqual(result, expected_result)

        # assert that delegate build strategy had been used with context
        delegate_build_strategy.__enter__.assert_called_once()
        delegate_build_strategy.__exit__.assert_called_once_with(ANY, ANY, ANY)

        # assert that delegate build strategy function methods have been called
        delegate_build_strategy.build_single_function_definition.assert_has_calls(
            [
                call(self.function_build_definition1),
                call(self.function_build_definition2),
            ]
        )

        # assert that delegate build strategy layer methods have been called
        delegate_build_strategy.build_single_layer_definition.assert_has_calls(
            [
                call(self.layer_build_definition1),
                call(self.layer_build_definition2),
            ]
        )


@patch("samcli.lib.build.build_strategy.os")
@patch("samcli.lib.build.build_strategy.DependencyHashGenerator")
class TestIncrementalBuildStrategy(TestCase):
    def setUp(self):
        self.build_function = Mock()
        self.build_layer = Mock()
        self.build_graph = Mock()
        self.delegate_build_strategy = DefaultBuildStrategy(
            self.build_graph, Mock(), self.build_function, self.build_layer, cached=True
        )
        self.build_strategy = IncrementalBuildStrategy(
            self.build_graph,
            self.delegate_build_strategy,
            Mock(),
            Mock(),
        )

    @parameterized.expand(
        list(
            itertools.product(
                [("hash1", "hash2"), ("hash1", "hash1")], [("existing_dir", True), ("missing_dir", False)]
            )
        )
    )
    def test_assert_incremental_build_function(self, patched_manifest_hash, patched_os, hashing_info, dependency_info):
        manifest_hash = hashing_info[0]
        build_toml_manifest_hash = hashing_info[1]
        dependency_dir = dependency_info[0]
        dependency_dir_exist = dependency_info[1]

        patched_os.path.exists.return_value = dependency_dir_exist

        patched_manifest_hash_instance = Mock(hash=manifest_hash)
        patched_manifest_hash.return_value = patched_manifest_hash_instance

        given_function_build_def = Mock(
            manifest_hash=build_toml_manifest_hash, functions=[Mock()], dependencies_dir=dependency_dir
        )
        self.build_graph.get_function_build_definitions.return_value = [given_function_build_def]
        self.build_graph.get_layer_build_definitions.return_value = []

        download_dependencies = manifest_hash != build_toml_manifest_hash or not dependency_dir_exist

        self.build_strategy.build()
        self.build_function.assert_called_with(
            ANY, ANY, ANY, ANY, ANY, ANY, ANY, ANY, ANY, dependency_dir, download_dependencies
        )

    @parameterized.expand(
        list(
            itertools.product(
                [("hash1", "hash2"), ("hash1", "hash1")], [("existing_dir", True), ("missing_dir", False)]
            )
        )
    )
    def test_assert_incremental_build_layer(self, patched_manifest_hash, patched_os, hashing_info, dependency_info):
        manifest_hash = hashing_info[0]
        build_toml_manifest_hash = hashing_info[1]
        dependency_dir = dependency_info[0]
        dependency_dir_exist = dependency_info[1]

        patched_os.path.exists.return_value = dependency_dir_exist

        patched_manifest_hash_instance = Mock(hash=manifest_hash)
        patched_manifest_hash.return_value = patched_manifest_hash_instance

        given_layer_build_def = Mock(
            manifest_hash=build_toml_manifest_hash, functions=[Mock()], dependencies_dir=dependency_dir
        )
        self.build_graph.get_function_build_definitions.return_value = []
        self.build_graph.get_layer_build_definitions.return_value = [given_layer_build_def]

        download_dependencies = manifest_hash != build_toml_manifest_hash or not dependency_dir_exist

        self.build_strategy.build()
        self.build_layer.assert_called_with(
            ANY, ANY, ANY, ANY, ANY, ANY, ANY, dependency_dir, download_dependencies, ANY
        )


@patch("samcli.lib.build.build_graph.BuildGraph._write")
@patch("samcli.lib.build.build_graph.BuildGraph._read")
class TestCachedOrIncrementalBuildStrategyWrapper(TestCase):
    def setUp(self) -> None:
        self.build_graph = BuildGraph("build/graph/location")

        self.build_strategy = CachedOrIncrementalBuildStrategyWrapper(
            self.build_graph,
            Mock(),
            "base_dir",
            "build_dir",
            "cache_dir",
            "manifest_path_override",
            False,
            False,
        )

    @parameterized.expand(
        [
            "python3.7",
            "nodejs12.x",
            "ruby2.7",
        ]
    )
    def test_will_call_incremental_build_strategy(self, mocked_read, mocked_write, runtime):
        build_definition = FunctionBuildDefinition(runtime, "codeuri", "packate_type", X86_64, {}, "handler")
        self.build_graph.put_function_build_definition(build_definition, Mock(full_path="function_full_path"))
        with patch.object(
            self.build_strategy, "_incremental_build_strategy"
        ) as patched_incremental_build_strategy, patch.object(
            self.build_strategy, "_cached_build_strategy"
        ) as patched_cached_build_strategy:
            self.build_strategy.build()

            patched_incremental_build_strategy.build_single_function_definition.assert_called_with(build_definition)
            patched_cached_build_strategy.assert_not_called()

    @parameterized.expand(
        [
            "dotnetcore3.1",
            "go1.x",
            "java11",
        ]
    )
    def test_will_call_cached_build_strategy(self, mocked_read, mocked_write, runtime):
        build_definition = FunctionBuildDefinition(runtime, "codeuri", "packate_type", X86_64, {}, "handler")
        self.build_graph.put_function_build_definition(build_definition, Mock(full_path="function_full_path"))
        with patch.object(
            self.build_strategy, "_incremental_build_strategy"
        ) as patched_incremental_build_strategy, patch.object(
            self.build_strategy, "_cached_build_strategy"
        ) as patched_cached_build_strategy:
            self.build_strategy.build()

            patched_cached_build_strategy.build_single_function_definition.assert_called_with(build_definition)
            patched_incremental_build_strategy.assert_not_called()

    @parameterized.expand([(True,), (False,)])
    @patch("samcli.lib.build.build_strategy.CachedBuildStrategy._clean_redundant_cached")
    @patch("samcli.lib.build.build_strategy.IncrementalBuildStrategy._clean_redundant_dependencies")
    def test_exit_build_strategy_for_specific_resource(
        self, is_building_specific_resource, clean_cache_mock, clean_dep_mock, mocked_read, mocked_write
    ):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            cache_dir = Path(temp_base_dir, ".aws-sam", "cache")
            cache_dir.mkdir(parents=True)

            mocked_build_graph = Mock()
            mocked_build_graph.get_layer_build_definitions.return_value = []
            mocked_build_graph.get_function_build_definitions.return_value = []

            cached_build_strategy = CachedOrIncrementalBuildStrategyWrapper(
                mocked_build_graph,
                Mock(),
                temp_base_dir,
                build_dir,
                cache_dir,
                None,
                is_building_specific_resource,
                False,
            )

            cached_build_strategy.build()

            if is_building_specific_resource:
                mocked_build_graph.update_definition_hash.assert_called_once()
                mocked_build_graph.clean_redundant_definitions_and_update.assert_not_called()
                clean_cache_mock.assert_not_called()
                clean_dep_mock.assert_not_called()
            else:
                mocked_build_graph.update_definition_hash.assert_not_called()
                mocked_build_graph.clean_redundant_definitions_and_update.assert_called_once()
                clean_cache_mock.assert_called_once()
                clean_dep_mock.assert_called_once()

    @parameterized.expand(
        [
            ("python", True),
            ("ruby", True),
            ("nodejs", True),
            ("python", False),
            ("ruby", False),
            ("nodejs", False),
        ]
    )
    def test_wrapper_with_or_without_container(self, mocked_read, mocked_write, runtime, use_container):
        build_strategy = CachedOrIncrementalBuildStrategyWrapper(
            self.build_graph,
            Mock(),
            "base_dir",
            "build_dir",
            "cache_dir",
            "manifest_path_override",
            False,
            use_container,
        )

        build_definition = FunctionBuildDefinition(runtime, "codeuri", "packate_type", X86_64, {}, "handler")
        self.build_graph.put_function_build_definition(build_definition, Mock(full_path="function_full_path"))
        with patch.object(
            build_strategy, "_incremental_build_strategy"
        ) as patched_incremental_build_strategy, patch.object(
            build_strategy, "_cached_build_strategy"
        ) as patched_cached_build_strategy:
            build_strategy.build()

            if not use_container:
                patched_incremental_build_strategy.build_single_function_definition.assert_called_with(build_definition)
                patched_cached_build_strategy.assert_not_called()
            else:
                patched_cached_build_strategy.build_single_function_definition.assert_called_with(build_definition)
                patched_incremental_build_strategy.assert_not_called()
