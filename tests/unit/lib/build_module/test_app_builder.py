import os
import posixpath
import sys

import docker
import json

from unittest import TestCase
from unittest.mock import Mock, MagicMock, call, patch, ANY
from pathlib import Path, WindowsPath

from parameterized import parameterized

from samcli.lib.providers.provider import ResourcesToBuildCollector, Function
from samcli.lib.build.app_builder import (
    ApplicationBuilder,
    UnsupportedBuilderLibraryVersionError,
    BuildError,
    LambdaBuilderError,
    ContainerBuildNotSupported,
    BuildInsideContainerError,
    DockerfileOutSideOfContext,
    DockerBuildFailed,
    DockerConnectionError,
)
from samcli.commands.local.cli_common.user_exceptions import InvalidFunctionPropertyType
from samcli.lib.utils.architecture import X86_64, ARM64
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.stream_writer import StreamWriter
from tests.unit.lib.build_module.test_build_graph import generate_function


class TestApplicationBuilder_build(TestCase):
    def setUp(self):
        self.build_dir = "builddir"

        self.func1 = MagicMock()
        self.func1.packagetype = ZIP
        self.func1.name = "function_name1"
        self.func1.full_path = posixpath.join("StackJ", "function_name1")
        self.func1.architectures = [X86_64]
        self.func1.get_build_dir = Mock()
        self.func1.inlinecode = None
        self.func2 = MagicMock()
        self.func2.packagetype = ZIP
        self.func2.name = "function_name2"
        self.func2.full_path = posixpath.join("StackJ", "function_name2")
        self.func2.architectures = [ARM64]
        self.func2.get_build_dir = Mock()
        self.func2.inlinecode = None
        self.imageFunc1 = MagicMock()
        self.imageFunc1.name = "function_name3"
        self.imageFunc1.full_path = posixpath.join("StackJ", "function_name3")
        self.imageFunc1.get_build_dir = Mock()
        self.imageFunc1.inlinecode = None
        self.imageFunc1.architectures = [X86_64]

        self.layer1 = Mock()
        self.layer2 = Mock()

        self.imageFunc1.packagetype = IMAGE
        self.layer1.build_method = "build_method"
        self.layer1.name = "layer_name1"
        self.layer1.full_path = os.path.join("StackJ", "layer_name1")
        self.layer1.get_build_dir = Mock()
        self.layer1.compatible_architectures = [X86_64]
        self.layer2.build_method = "build_method"
        self.layer2.name = "layer_name2"
        self.layer2.full_path = os.path.join("StackJ", "layer_name2")
        self.layer2.compatible_architectures = [X86_64]
        self.layer2.get_build_dir = Mock()

        resources_to_build_collector = ResourcesToBuildCollector()
        resources_to_build_collector.add_functions([self.func1, self.func2, self.imageFunc1])
        resources_to_build_collector.add_layers([self.layer1, self.layer2])
        self.builder = ApplicationBuilder(
            resources_to_build_collector, "builddir", "basedir", "cachedir", stream_writer=StreamWriter(sys.stderr)
        )

    @patch("samcli.lib.build.build_graph.BuildGraph._write")
    def test_must_iterate_on_functions_and_layers(self, persist_mock):
        build_function_mock = Mock()
        build_image_function_mock = Mock()
        build_image_function_mock_return = Mock()
        build_layer_mock = Mock()

        def build_layer_return(
            layer_name,
            layer_codeuri,
            layer_build_method,
            layer_compatible_runtimes,
            layer_build_architecture,
            artifact_dir,
            layer_env_vars,
            dependencies_dir,
            download_dependencies,
        ):
            return f"{layer_name}_location"

        build_layer_mock.side_effect = build_layer_return

        self.builder._build_function = build_function_mock
        self.builder._build_lambda_image = build_image_function_mock
        self.builder._build_layer = build_layer_mock

        build_function_mock.side_effect = [
            os.path.join(self.build_dir, "StackJ", "function_name1"),
            os.path.join(self.build_dir, "StackJ", "function_name2"),
            build_image_function_mock_return,
        ]

        result = self.builder.build().artifacts
        self.maxDiff = None

        self.assertEqual(
            result,
            {
                self.func1.full_path: os.path.join("builddir", "StackJ", "function_name1"),
                self.func2.full_path: os.path.join("builddir", "StackJ", "function_name2"),
                self.imageFunc1.full_path: build_image_function_mock_return,
                self.layer1.full_path: f"{self.layer1.name}_location",
                self.layer2.full_path: f"{self.layer2.name}_location",
            },
        )

        build_function_mock.assert_has_calls(
            [
                call(
                    self.func1.name,
                    self.func1.codeuri,
                    ZIP,
                    self.func1.runtime,
                    self.func1.architecture,
                    self.func1.handler,
                    ANY,
                    self.func1.metadata,
                    ANY,
                    ANY,
                    True,
                ),
                call(
                    self.func2.name,
                    self.func2.codeuri,
                    ZIP,
                    self.func2.runtime,
                    self.func2.architecture,
                    self.func2.handler,
                    ANY,
                    self.func2.metadata,
                    ANY,
                    ANY,
                    True,
                ),
                call(
                    self.imageFunc1.name,
                    self.imageFunc1.codeuri,
                    IMAGE,
                    self.imageFunc1.runtime,
                    self.imageFunc1.architecture,
                    self.imageFunc1.handler,
                    ANY,
                    self.imageFunc1.metadata,
                    ANY,
                    ANY,
                    True,
                ),
            ],
            any_order=False,
        )

        build_layer_mock.assert_has_calls(
            [
                call(
                    self.layer1.name,
                    self.layer1.codeuri,
                    self.layer1.build_method,
                    self.layer1.compatible_runtimes,
                    self.layer1.build_architecture,
                    ANY,
                    ANY,
                    ANY,
                    True,
                ),
                call(
                    self.layer2.name,
                    self.layer2.codeuri,
                    self.layer2.build_method,
                    self.layer2.compatible_runtimes,
                    self.layer2.build_architecture,
                    ANY,
                    ANY,
                    ANY,
                    True,
                ),
            ]
        )

    @patch("samcli.lib.build.build_graph.BuildGraph._write")
    def test_should_use_function_or_layer_get_build_dir_to_determine_artifact_dir(self, persist_mock):
        def get_func_call_with_artifact_dir(artifact_dir):
            return call(ANY, ANY, ANY, ANY, ANY, ANY, artifact_dir, ANY, ANY, ANY, True)

        def get_layer_call_with_artifact_dir(artifact_dir):
            return call(ANY, ANY, ANY, ANY, ANY, artifact_dir, ANY, ANY, True)

        build_function_mock = Mock()
        build_layer_mock = Mock()
        self.builder._build_function = build_function_mock
        self.builder._build_layer = build_layer_mock

        self.builder.build()

        # make sure function/layer's get_build_dir() is called with correct directory
        self.func1.get_build_dir.assert_called_with(self.build_dir)
        self.func2.get_build_dir.assert_called_with(self.build_dir)
        self.imageFunc1.get_build_dir.assert_called_with(self.build_dir)
        self.layer1.get_build_dir.assert_called_with(self.build_dir)
        self.layer2.get_build_dir.assert_called_with(self.build_dir)

        # make sure whatever is returned from .get_build_dir() is used for build function/layer
        build_function_mock.assert_has_calls(
            [
                get_func_call_with_artifact_dir(self.func1.get_build_dir()),
                get_func_call_with_artifact_dir(self.func2.get_build_dir()),
                get_func_call_with_artifact_dir(self.imageFunc1.get_build_dir()),
            ]
        )

        build_layer_mock.assert_has_calls(
            [
                get_layer_call_with_artifact_dir(self.layer1.get_build_dir()),
                get_layer_call_with_artifact_dir(self.layer2.get_build_dir()),
            ]
        )

    @patch("samcli.lib.build.build_graph.BuildGraph._write")
    def test_should_generate_build_graph(self, persist_mock):
        build_graph = self.builder._get_build_graph()

        self.assertTrue(len(build_graph.get_function_build_definitions()), 2)

        all_functions_in_build_graph = []
        for build_definition in build_graph.get_function_build_definitions():
            for function in build_definition.functions:
                all_functions_in_build_graph.append(function)

        self.assertTrue(self.func1 in all_functions_in_build_graph)
        self.assertTrue(self.func2 in all_functions_in_build_graph)

    @patch("samcli.lib.build.build_graph.BuildGraph._write")
    @patch("samcli.lib.build.build_graph.BuildGraph._read")
    @patch("samcli.lib.build.build_strategy.osutils")
    def test_should_run_build_for_only_unique_builds(self, persist_mock, read_mock, osutils_mock):
        build_function_mock = Mock()

        # create 3 function resources where 2 of them would have same codeuri, runtime and metadata
        function1_1 = generate_function(name="function1_1")
        function1_2 = generate_function(name="function1_2")
        function2 = generate_function(name="function2", runtime="different_runtime")
        resources_to_build_collector = ResourcesToBuildCollector()
        resources_to_build_collector.add_functions([function1_1, function1_2, function2])

        build_dir = "builddir"

        # instantiate the builder and run build method
        builder = ApplicationBuilder(
            resources_to_build_collector, "builddir", "basedir", "cachedir", stream_writer=StreamWriter(sys.stderr)
        )
        builder._build_function = build_function_mock
        build_function_mock.side_effect = [
            function1_1.get_build_dir(build_dir),
            function1_2.get_build_dir(build_dir),
            function1_2.get_build_dir(build_dir),
        ]

        result = builder.build().artifacts

        # result should contain all 3 functions as expected
        self.assertEqual(
            result,
            {
                function1_1.full_path: function1_1.get_build_dir(build_dir),
                function1_2.full_path: function1_2.get_build_dir(build_dir),
                function2.full_path: function1_2.get_build_dir(build_dir),
            },
        )

        # actual build should only be called twice since only 2 of the functions have unique build
        build_function_mock.assert_has_calls(
            [
                call(
                    function1_1.name,
                    function1_1.codeuri,
                    ZIP,
                    function1_1.runtime,
                    function1_1.architectures[0],
                    function1_1.handler,
                    ANY,
                    function1_1.metadata,
                    ANY,
                    ANY,
                    True,
                ),
                call(
                    function2.name,
                    function2.codeuri,
                    ZIP,
                    function2.runtime,
                    function1_1.architectures[0],
                    function2.handler,
                    ANY,
                    function2.metadata,
                    ANY,
                    ANY,
                    True,
                ),
            ],
            any_order=True,
        )

    @patch("samcli.lib.build.app_builder.DefaultBuildStrategy")
    def test_default_run_should_pick_default_strategy(self, mock_default_build_strategy_class):
        mock_default_build_strategy = Mock()
        mock_default_build_strategy_class.return_value = mock_default_build_strategy

        build_graph_mock = Mock()
        get_build_graph_mock = Mock(return_value=build_graph_mock)

        builder = ApplicationBuilder(Mock(), "builddir", "basedir", "cachedir", stream_writer=StreamWriter(sys.stderr))
        builder._get_build_graph = get_build_graph_mock

        result = builder.build().artifacts

        mock_default_build_strategy.build.assert_called_once()
        self.assertEqual(result, mock_default_build_strategy.build())

    @patch("samcli.lib.build.app_builder.CachedOrIncrementalBuildStrategyWrapper")
    def test_cached_run_should_pick_incremental_strategy(
        self,
        mock_cached_and_incremental_build_strategy_class,
    ):
        mock_cached_and_incremental_build_strategy = Mock()
        mock_cached_and_incremental_build_strategy_class.return_value = mock_cached_and_incremental_build_strategy

        build_graph_mock = Mock()
        get_build_graph_mock = Mock(return_value=build_graph_mock)

        builder = ApplicationBuilder(
            Mock(), "builddir", "basedir", "cachedir", cached=True, stream_writer=StreamWriter(sys.stderr)
        )
        builder._get_build_graph = get_build_graph_mock

        result = builder.build().artifacts

        mock_cached_and_incremental_build_strategy.build.assert_called_once()
        self.assertEqual(result, mock_cached_and_incremental_build_strategy.build())

    @patch("samcli.lib.build.app_builder.ParallelBuildStrategy")
    def test_parallel_run_should_pick_parallel_strategy(self, mock_parallel_build_strategy_class):
        mock_parallel_build_strategy = Mock()
        mock_parallel_build_strategy_class.return_value = mock_parallel_build_strategy

        build_graph_mock = Mock()
        get_build_graph_mock = Mock(return_value=build_graph_mock)

        builder = ApplicationBuilder(
            Mock(), "builddir", "basedir", "cachedir", parallel=True, stream_writer=StreamWriter(sys.stderr)
        )
        builder._get_build_graph = get_build_graph_mock

        result = builder.build().artifacts

        mock_parallel_build_strategy.build.assert_called_once()
        self.assertEqual(result, mock_parallel_build_strategy.build())

    @patch("samcli.lib.build.app_builder.ParallelBuildStrategy")
    @patch("samcli.lib.build.app_builder.CachedOrIncrementalBuildStrategyWrapper")
    def test_parallel_and_cached_run_should_pick_parallel_with_incremental(
        self,
        mock_cached_and_incremental_build_strategy_class,
        mock_parallel_build_strategy_class,
    ):
        mock_cached_and_incremental_build_strategy = Mock()
        mock_cached_and_incremental_build_strategy_class.return_value = mock_cached_and_incremental_build_strategy
        mock_parallel_build_strategy = Mock()
        mock_parallel_build_strategy_class.return_value = mock_parallel_build_strategy

        build_graph_mock = Mock()
        get_build_graph_mock = Mock(return_value=build_graph_mock)

        builder = ApplicationBuilder(
            Mock(),
            "builddir",
            "basedir",
            "cachedir",
            parallel=True,
            cached=True,
            stream_writer=StreamWriter(sys.stderr),
        )
        builder._get_build_graph = get_build_graph_mock

        result = builder.build().artifacts

        mock_parallel_build_strategy_class.assert_called_once_with(ANY, mock_cached_and_incremental_build_strategy)

        mock_parallel_build_strategy.build.assert_called_once()
        self.assertEqual(result, mock_parallel_build_strategy.build())

    @patch("samcli.lib.build.build_graph.BuildGraph._write")
    @patch("samcli.lib.build.build_graph.BuildGraph._read")
    @patch("samcli.lib.build.build_strategy.osutils")
    def test_must_raise_for_functions_with_multi_architecture(self, persist_mock, read_mock, osutils_mock):
        build_function_mock = Mock()

        function = Function(
            function_id="name",
            name="name",
            functionname="function_name",
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
            architectures=[X86_64, ARM64],
            stack_path="",
        )

        resources_to_build_collector = ResourcesToBuildCollector()
        resources_to_build_collector.add_functions([function])

        build_dir = "builddir"

        # instantiate the builder and run build method
        builder = ApplicationBuilder(
            resources_to_build_collector, "builddir", "basedir", "cachedir", stream_writer=StreamWriter(sys.stderr)
        )
        builder._build_function = build_function_mock
        build_function_mock.side_effect = [function.get_build_dir(build_dir)]

        with self.assertRaises(InvalidFunctionPropertyType) as ex:
            builder.build()
        msg = "Function name property Architectures should be a list of length 1"
        self.assertEqual(str(ex.exception), msg)


class PathValidator:
    def __init__(self, path):
        self._path = path

    def __eq__(self, other):
        return self._path is None if other is None else other.endswith(self._path)


class TestApplicationBuilderForLayerBuild(TestCase):
    def setUp(self):
        self.layer1 = Mock()
        self.layer2 = Mock()
        self.container_manager = Mock()
        resources_to_build_collector = ResourcesToBuildCollector()
        resources_to_build_collector.add_layers([self.layer1, self.layer2])
        self.builder = ApplicationBuilder(
            resources_to_build_collector, "builddir", "basedir", "cachedir", stream_writer=StreamWriter(sys.stderr)
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    @patch("samcli.lib.build.app_builder.get_layer_subfolder")
    def test_must_build_layer_in_process(self, get_layer_subfolder_mock, osutils_mock, get_workflow_config_mock):
        get_layer_subfolder_mock.return_value = "python"
        config_mock = Mock()
        config_mock.manifest_name = "manifest_name"

        scratch_dir = "scratch"
        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        get_workflow_config_mock.return_value = config_mock
        build_function_in_process_mock = Mock()

        self.builder._build_function_in_process = build_function_in_process_mock
        self.builder._build_layer("layer_name", "code_uri", "python3.8", ["python3.8"], ARM64, "full_path")

        build_function_in_process_mock.assert_called_once_with(
            config_mock,
            PathValidator("code_uri"),
            PathValidator("python"),
            "scratch",
            PathValidator("manifest_name"),
            "python3.8",
            ARM64,
            None,
            None,
            True,
            True,
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    @patch("samcli.lib.build.app_builder.get_layer_subfolder")
    def test_must_build_layer_in_container(self, get_layer_subfolder_mock, osutils_mock, get_workflow_config_mock):
        self.builder._container_manager = self.container_manager
        get_layer_subfolder_mock.return_value = "python"
        config_mock = Mock()
        config_mock.manifest_name = "manifest_name"

        scratch_dir = "scratch"
        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        get_workflow_config_mock.return_value = config_mock
        build_function_on_container_mock = Mock()

        self.builder._build_function_on_container = build_function_on_container_mock
        self.builder._build_layer("layer_name", "code_uri", "python3.8", ["python3.8"], X86_64, "full_path")
        build_function_on_container_mock.assert_called_once_with(
            config_mock,
            PathValidator("code_uri"),
            PathValidator("python"),
            PathValidator("manifest_name"),
            "python3.8",
            X86_64,
            None,
            None,
            None,
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    @patch("samcli.lib.build.app_builder.get_layer_subfolder")
    def test_must_build_layer_in_container_with_global_build_image(
        self, get_layer_subfolder_mock, osutils_mock, get_workflow_config_mock
    ):
        self.builder._container_manager = self.container_manager
        get_layer_subfolder_mock.return_value = "python"
        config_mock = Mock()
        config_mock.manifest_name = "manifest_name"

        scratch_dir = "scratch"
        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        get_workflow_config_mock.return_value = config_mock
        build_function_on_container_mock = Mock()

        build_images = {None: "test_image"}
        self.builder._build_images = build_images
        self.builder._build_function_on_container = build_function_on_container_mock
        self.builder._build_layer("layer_name", "code_uri", "python3.8", ["python3.8"], X86_64, "full_path")
        build_function_on_container_mock.assert_called_once_with(
            config_mock,
            PathValidator("code_uri"),
            PathValidator("python"),
            PathValidator("manifest_name"),
            "python3.8",
            X86_64,
            None,
            None,
            "test_image",
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    @patch("samcli.lib.build.app_builder.get_layer_subfolder")
    def test_must_build_layer_in_container_with_specific_build_image(
        self, get_layer_subfolder_mock, osutils_mock, get_workflow_config_mock
    ):
        self.builder._container_manager = self.container_manager
        get_layer_subfolder_mock.return_value = "python"
        config_mock = Mock()
        config_mock.manifest_name = "manifest_name"

        scratch_dir = "scratch"
        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        get_workflow_config_mock.return_value = config_mock
        build_function_on_container_mock = Mock()

        build_images = {"layer_name": "test_image"}
        self.builder._build_images = build_images
        self.builder._build_function_on_container = build_function_on_container_mock
        self.builder._build_layer("layer_name", "code_uri", "python3.8", ["python3.8"], ARM64, "full_path")
        build_function_on_container_mock.assert_called_once_with(
            config_mock,
            PathValidator("code_uri"),
            PathValidator("python"),
            PathValidator("manifest_name"),
            "python3.8",
            ARM64,
            None,
            None,
            "test_image",
        )


class TestApplicationBuilder_update_template(TestCase):
    def make_root_template(self, resource_type, location_property_name):
        return {
            "Resources": {
                "MyFunction1": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "oldvalue"}},
                "ChildStackXXX": {"Type": resource_type, "Properties": {location_property_name: "./child.yaml"}},
            }
        }

    def setUp(self):
        self.builder = ApplicationBuilder(
            Mock(), "builddir", "basedir", "cachedir", stream_writer=StreamWriter(sys.stderr)
        )

        self.template_dict = {
            "Resources": {
                "MyFunction1": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "oldvalue"}},
                "MyFunction2": {"Type": "AWS::Lambda::Function", "Properties": {"Code": "oldvalue"}},
                "MyCDKFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "aws:cdk:path": "Stack/CDKFunc/Resource",
                    },
                },
                "MyCustomIdFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "SamResourceId": "CustomIdFunc",
                    },
                },
                "SkipMyCDKFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "aws:cdk:path": "Stack/SkipCDKFunc/Resource",
                        "aws:asset:is-bundled": True,
                    },
                },
                "SkipMyCustomIdFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "SamResourceId": "SkipCustomIdFunc",
                        "SkipBuild": True,
                    },
                },
                "GlueResource": {"Type": "AWS::Glue::Job", "Properties": {"Command": {"ScriptLocation": "something"}}},
                "OtherResource": {"Type": "AWS::Lambda::Version", "Properties": {"CodeUri": "something"}},
                "MyImageFunction1": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"PackageType": "Image"},
                    "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "DockerContext", "DockerTag": "Tag"},
                },
                "MyServerlessLayer": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {"ContentUri": "oldvalue"},
                    "Metadata": {"BuildMethod": "python3.8"},
                },
                "MyLambdaLayer": {
                    "Type": "AWS::Lambda::LayerVersion",
                    "Properties": {"Content": "oldvalue"},
                    "Metadata": {"BuildMethod": "python3.8"},
                },
            }
        }

    def test_must_update_resources_with_build_artifacts(self):
        self.maxDiff = None
        original_template_path = "/path/to/tempate.txt"
        built_artifacts = {
            "MyFunction1": "/path/to/build/MyFunction1",
            "MyFunction2": "/path/to/build/MyFunction2",
            "CDKFunc": "/path/to/build/MyCDKFunction",
            "CustomIdFunc": "/path/to/build/MyCustomIdFunction",
            "MyServerlessLayer": "/path/to/build/ServerlessLayer",
            "MyLambdaLayer": "/path/to/build/LambdaLayer",
            "MyImageFunction1": "myimagefunction1:Tag",
            "PreBuiltImageFunction1": "",
        }

        expected_result = {
            "Resources": {
                "MyFunction1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": os.path.join("build", "MyFunction1")},
                },
                "MyFunction2": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": os.path.join("build", "MyFunction2")},
                },
                "MyCDKFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": os.path.join("build", "MyCDKFunction")},
                    "Metadata": {
                        "Normalized": True,
                        "aws:cdk:path": "Stack/CDKFunc/Resource",
                    },
                },
                "MyCustomIdFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": os.path.join("build", "MyCustomIdFunction")},
                    "Metadata": {
                        "Normalized": True,
                        "SamResourceId": "CustomIdFunc",
                    },
                },
                "SkipMyCDKFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "aws:cdk:path": "Stack/SkipCDKFunc/Resource",
                        "aws:asset:is-bundled": True,
                    },
                },
                "SkipMyCustomIdFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "SamResourceId": "SkipCustomIdFunc",
                        "SkipBuild": True,
                    },
                },
                "GlueResource": {"Type": "AWS::Glue::Job", "Properties": {"Command": {"ScriptLocation": "something"}}},
                "OtherResource": {"Type": "AWS::Lambda::Version", "Properties": {"CodeUri": "something"}},
                "MyImageFunction1": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": {"ImageUri": "myimagefunction1:Tag"}, "PackageType": IMAGE},
                    "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "DockerContext", "DockerTag": "Tag"},
                },
                "MyServerlessLayer": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {"ContentUri": os.path.join("build", "ServerlessLayer")},
                    "Metadata": {"BuildMethod": "python3.8"},
                },
                "MyLambdaLayer": {
                    "Type": "AWS::Lambda::LayerVersion",
                    "Properties": {"Content": os.path.join("build", "LambdaLayer")},
                    "Metadata": {"BuildMethod": "python3.8"},
                },
            }
        }

        stack = Mock(stack_path="", template_dict=self.template_dict, location=original_template_path)
        stack.resources = {
            "MyCDKFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": os.path.join("build", "MyCDKFunction")},
                "Metadata": {
                    "Normalized": True,
                    "aws:cdk:path": "Stack/CDKFunc/Resource",
                },
            },
            "MyCustomIdFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": os.path.join("build", "MyCustomIdFunction")},
                "Metadata": {
                    "Normalized": True,
                    "SamResourceId": "CustomIdFunc",
                },
            },
        }
        actual = self.builder.update_template(stack, built_artifacts, {})
        self.assertEqual(actual, expected_result)

    @parameterized.expand([("AWS::Serverless::Application", "Location"), ("AWS::CloudFormation::Stack", "TemplateURL")])
    def test_must_update_resources_with_build_artifacts_and_template_paths_in_multi_stack(
        self, resource_type, location_property_name
    ):
        self.maxDiff = None
        original_child_template_path = "/path/to/child.yaml"
        original_root_template_path = "/path/to/template.yaml"
        built_artifacts = {
            "MyFunction1": "/path/to/build/MyFunction1",
            "ChildStackXXX/MyServerlessLayer": "/path/to/build/ChildStackXXX/ServerlessLayer",
            "ChildStackXXX/MyLambdaLayer": "/path/to/build/ChildStackXXX/LambdaLayer",
            "ChildStackXXX/MyFunction1": "/path/to/build/ChildStackXXX/MyFunction1",
            "ChildStackXXX/MyFunction2": "/path/to/build/ChildStackXXX/MyFunction2",
            "ChildStackXXX/CDKFunc": "/path/to/build/ChildStackXXX/MyCDKFunction",
            "ChildStackXXX/CustomIdFunc": "/path/to/build/ChildStackXXX/MyCustomIdFunction",
            "ChildStackXXX/MyImageFunction1": "myimagefunction1:Tag",
        }
        stack_output_paths = {
            "": "/path/to/build/template.yaml",
            "ChildStackXXX": "/path/to/build/ChildStackXXX/template.yaml",
        }

        expected_child = {
            "Resources": {
                "MyFunction1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": os.path.join("build", "ChildStackXXX", "MyFunction1")},
                },
                "MyFunction2": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": os.path.join("build", "ChildStackXXX", "MyFunction2")},
                },
                "MyCDKFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": os.path.join("build", "ChildStackXXX", "MyCDKFunction")},
                    "Metadata": {
                        "aws:cdk:path": "Stack/CDKFunc/Resource",
                    },
                },
                "MyCustomIdFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": os.path.join("build", "ChildStackXXX", "MyCustomIdFunction")},
                    "Metadata": {
                        "SamResourceId": "CustomIdFunc",
                    },
                },
                "SkipMyCDKFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "aws:cdk:path": "Stack/SkipCDKFunc/Resource",
                        "aws:asset:is-bundled": True,
                    },
                },
                "SkipMyCustomIdFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": "oldvalue"},
                    "Metadata": {
                        "SamResourceId": "SkipCustomIdFunc",
                        "SkipBuild": True,
                    },
                },
                "GlueResource": {"Type": "AWS::Glue::Job", "Properties": {"Command": {"ScriptLocation": "something"}}},
                "OtherResource": {"Type": "AWS::Lambda::Version", "Properties": {"CodeUri": "something"}},
                "MyImageFunction1": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": {"ImageUri": "myimagefunction1:Tag"}, "PackageType": IMAGE},
                    "Metadata": {"Dockerfile": "Dockerfile", "DockerContext": "DockerContext", "DockerTag": "Tag"},
                },
                "MyServerlessLayer": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {"ContentUri": os.path.join("build", "ChildStackXXX", "ServerlessLayer")},
                    "Metadata": {"BuildMethod": "python3.8"},
                },
                "MyLambdaLayer": {
                    "Type": "AWS::Lambda::LayerVersion",
                    "Properties": {"Content": os.path.join("build", "ChildStackXXX", "LambdaLayer")},
                    "Metadata": {"BuildMethod": "python3.8"},
                },
            }
        }
        expected_root = {
            "Resources": {
                "MyFunction1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": os.path.join("build", "MyFunction1")},
                },
                "ChildStackXXX": {
                    "Type": resource_type,
                    "Properties": {
                        location_property_name: os.path.join("build", "ChildStackXXX", "template.yaml"),
                    },
                },
            }
        }

        stack_root = Mock(
            stack_path="",
            template_dict=self.make_root_template(resource_type, location_property_name),
            location=original_root_template_path,
        )
        stack_root.resources = {}
        actual_root = self.builder.update_template(stack_root, built_artifacts, stack_output_paths)
        stack_child = Mock(
            stack_path="ChildStackXXX",
            template_dict=self.template_dict,
            location=original_child_template_path,
        )
        stack_child.resources = {}
        actual_child = self.builder.update_template(stack_child, built_artifacts, stack_output_paths)
        self.assertEqual(expected_root, actual_root)
        self.assertEqual(expected_child, actual_child)

    def test_must_skip_if_no_artifacts(self):
        built_artifacts = {}
        stack = Mock(stack_path="", template_dict=self.template_dict, location="/foo/bar/template.txt")
        actual = self.builder.update_template(stack, built_artifacts, {})

        self.assertEqual(actual, self.template_dict)


class TestApplicationBuilder_update_template_windows(TestCase):
    def setUp(self):
        self.builder = ApplicationBuilder(
            Mock(), "builddir", "basedir", "cachedir", stream_writer=StreamWriter(sys.stderr)
        )

        self.template_dict = {
            "Resources": {
                "MyFunction1": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "oldvalue"}},
                "MyFunction2": {"Type": "AWS::Lambda::Function", "Properties": {"Code": "oldvalue"}},
                "GlueResource": {"Type": "AWS::Glue::Job", "Properties": {"Command": {"ScriptLocation": "something"}}},
                "OtherResource": {"Type": "AWS::Lambda::Version", "Properties": {"CodeUri": "something"}},
                "ChildStack1": {"Type": "AWS::Serverless::Application", "Properties": {"Location": "oldvalue"}},
                "ChildStack2": {"Type": "AWS::CloudFormation::Stack", "Properties": {"TemplateURL": "oldvalue"}},
            }
        }

        # Force os.path to be ntpath instead of posixpath on unix systems
        import ntpath

        self.saved_os_path_module = sys.modules["os.path"]
        os.path = sys.modules["ntpath"]

    def test_must_write_absolute_path_for_different_drives(self):
        def mock_new(cls, *args, **kwargs):
            cls = WindowsPath
            self = cls._from_parts(args, init=False)
            self._init()
            return self

        def mock_resolve(self):
            return self

        with patch("pathlib.Path.__new__", new=mock_new):
            with patch("pathlib.Path.resolve", new=mock_resolve):
                original_template_path = "C:\\path\\to\\template.txt"
                function_1_path = "D:\\path\\to\\build\\MyFunction1"
                function_2_path = "C:\\path2\\to\\build\\MyFunction2"
                built_artifacts = {"MyFunction1": function_1_path, "MyFunction2": function_2_path}
                child_1_path = "D:\\path\\to\\build\\ChildStack1\\template.yaml"
                child_2_path = "C:\\path2\\to\\build\\ChildStack2\\template.yaml"
                output_template_paths = {"ChildStack1": child_1_path, "ChildStack2": child_2_path}

                expected_result = {
                    "Resources": {
                        "MyFunction1": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": function_1_path},
                        },
                        "MyFunction2": {
                            "Type": "AWS::Lambda::Function",
                            "Properties": {"Code": "..\\..\\path2\\to\\build\\MyFunction2"},
                        },
                        "GlueResource": {
                            "Type": "AWS::Glue::Job",
                            "Properties": {"Command": {"ScriptLocation": "something"}},
                        },
                        "OtherResource": {"Type": "AWS::Lambda::Version", "Properties": {"CodeUri": "something"}},
                        "ChildStack1": {
                            "Type": "AWS::Serverless::Application",
                            "Properties": {"Location": child_1_path},
                        },
                        "ChildStack2": {
                            "Type": "AWS::CloudFormation::Stack",
                            "Properties": {"TemplateURL": "..\\..\\path2\\to\\build\\ChildStack2\\template.yaml"},
                        },
                    }
                }

                stack = Mock()
                stack.stack_path = ""
                stack.template_dict = self.template_dict
                stack.location = original_template_path
                stack.resources = {}

                actual = self.builder.update_template(stack, built_artifacts, output_template_paths)
                self.assertEqual(actual, expected_result)

    def tearDown(self):
        os.path = self.saved_os_path_module


class TestApplicationBuilder_build_lambda_image_function(TestCase):
    def setUp(self):
        self.stream_mock = Mock()
        self.docker_client_mock = Mock()
        self.builder = ApplicationBuilder(
            Mock(),
            "/build/dir",
            "/base/dir",
            "/cached/dir",
            stream_writer=self.stream_mock,
            docker_client=self.docker_client_mock,
        )

    def test_docker_build_raises_docker_unavailable(self):
        with self.assertRaises(DockerConnectionError):
            metadata = {
                "Dockerfile": "Dockerfile",
                "DockerContext": "context",
                "DockerTag": "Tag",
                "DockerBuildArgs": {"a": "b"},
            }

            self.docker_client_mock.ping.side_effect = docker.errors.APIError(message="Mock Error")

            self.builder._build_lambda_image("Name", metadata, X86_64)

    def test_docker_build_raises_DockerBuildFailed_when_error_in_buildlog_stream(self):
        with self.assertRaises(DockerBuildFailed):
            metadata = {
                "Dockerfile": "Dockerfile",
                "DockerContext": "context",
                "DockerTag": "Tag",
                "DockerBuildArgs": {"a": "b"},
            }

            self.docker_client_mock.api.build.return_value = [{"error": "Function building failed"}]

            self.builder._build_lambda_image("Name", metadata, X86_64)

    def test_dockerfile_not_in_dockercontext(self):
        with self.assertRaises(DockerfileOutSideOfContext):
            metadata = {
                "Dockerfile": "Dockerfile",
                "DockerContext": "context",
                "DockerTag": "Tag",
                "DockerBuildArgs": {"a": "b"},
            }

            response_mock = Mock()
            response_mock.status_code = 500
            error_mock = Mock()
            error_mock.side_effect = docker.errors.APIError(
                "Bad Request", response=response_mock, explanation="Cannot locate specified Dockerfile"
            )
            self.builder._stream_lambda_image_build_logs = error_mock
            self.docker_client_mock.api.build.return_value = []

            self.builder._build_lambda_image("Name", metadata, X86_64)

    def test_error_rerasises(self):
        with self.assertRaises(docker.errors.APIError):
            metadata = {
                "Dockerfile": "Dockerfile",
                "DockerContext": "context",
                "DockerTag": "Tag",
                "DockerBuildArgs": {"a": "b"},
            }
            error_mock = Mock()
            error_mock.side_effect = docker.errors.APIError("Bad Request", explanation="Some explanation")
            self.builder._stream_lambda_image_build_logs = error_mock
            self.docker_client_mock.api.build.return_value = []

            self.builder._build_lambda_image("Name", metadata, X86_64)

    def test_can_build_image_function(self):
        metadata = {
            "Dockerfile": "Dockerfile",
            "DockerContext": "context",
            "DockerTag": "Tag",
            "DockerBuildArgs": {"a": "b"},
        }

        self.docker_client_mock.api.build.return_value = []

        result = self.builder._build_lambda_image("Name", metadata, X86_64)

        self.assertEqual(result, "name:Tag")

    def test_build_image_function_without_docker_file_raises_Docker_Build_Failed_Exception(self):
        metadata = {
            "DockerContext": "context",
            "DockerTag": "Tag",
            "DockerBuildArgs": {"a": "b"},
        }

        with self.assertRaises(DockerBuildFailed):
            self.builder._build_lambda_image("Name", metadata, X86_64)

        self.docker_client_mock.api.build.assert_not_called()

    def test_build_image_function_without_docker_context_raises_Docker_Build_Failed_Exception(self):
        metadata = {
            "DockerFIle": "Dockerfile",
            "DockerTag": "Tag",
            "DockerBuildArgs": {"a": "b"},
        }

        with self.assertRaises(DockerBuildFailed):
            self.builder._build_lambda_image("Name", metadata, X86_64)

        self.docker_client_mock.api.build.assert_not_called()

    def test_build_image_function_with_empty_metadata_raises_Docker_Build_Failed_Exception(self):
        metadata = {}

        with self.assertRaises(DockerBuildFailed):
            self.builder._build_lambda_image("Name", metadata, X86_64)

        self.docker_client_mock.api.build.assert_not_called()

    def test_can_build_image_function_without_tag(self):
        metadata = {"Dockerfile": "Dockerfile", "DockerContext": "context", "DockerBuildArgs": {"a": "b"}}

        self.docker_client_mock.api.build.return_value = []
        result = self.builder._build_lambda_image("Name", metadata, X86_64)

        self.assertEqual(result, "name:latest")

    @patch("samcli.lib.build.app_builder.os")
    def test_can_build_image_function_under_debug(self, mock_os):
        mock_os.environ.get.return_value = "debug"
        metadata = {
            "Dockerfile": "Dockerfile",
            "DockerContext": "context",
            "DockerTag": "Tag",
            "DockerBuildArgs": {"a": "b"},
        }

        self.docker_client_mock.api.build.return_value = []

        result = self.builder._build_lambda_image("Name", metadata, X86_64)
        self.assertEqual(result, "name:Tag-debug")
        self.assertEqual(
            self.docker_client_mock.api.build.call_args,
            # NOTE (sriram-mv): path set to ANY to handle platform differences.
            call(
                path=ANY,
                dockerfile="Dockerfile",
                tag="name:Tag-debug",
                buildargs={"a": "b", "SAM_BUILD_MODE": "debug"},
                decode=True,
                platform="linux/amd64",
            ),
        )

    @patch("samcli.lib.build.app_builder.os")
    def test_can_build_image_function_under_debug_with_target(self, mock_os):
        mock_os.environ.get.return_value = "debug"
        metadata = {
            "Dockerfile": "Dockerfile",
            "DockerContext": "context",
            "DockerTag": "Tag",
            "DockerBuildArgs": {"a": "b"},
            "DockerBuildTarget": "stage",
        }

        self.docker_client_mock.api.build.return_value = []

        result = self.builder._build_lambda_image("Name", metadata, X86_64)
        self.assertEqual(result, "name:Tag-debug")
        self.assertEqual(
            self.docker_client_mock.api.build.call_args,
            call(
                path=ANY,
                dockerfile="Dockerfile",
                tag="name:Tag-debug",
                buildargs={"a": "b", "SAM_BUILD_MODE": "debug"},
                decode=True,
                target="stage",
                platform="linux/amd64",
            ),
        )


class TestApplicationBuilder_build_function(TestCase):
    def setUp(self):
        self.builder = ApplicationBuilder(
            Mock(), "/build/dir", "/base/dir", "cachedir", stream_writer=StreamWriter(sys.stderr)
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_process(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        packagetype = ZIP
        runtime = "runtime"
        architecture = X86_64
        scratch_dir = "scratch"
        handler = "handler.handle"
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_in_process = Mock()

        code_dir = str(Path("/base/dir/path/to/source").resolve())
        artifacts_dir = str(Path("/build/dir/function_full_path"))
        manifest_path = str(Path(os.path.join(code_dir, config_mock.manifest_name)).resolve())

        self.builder._build_function(function_name, codeuri, ZIP, runtime, architecture, handler, artifacts_dir)

        self.builder._build_function_in_process.assert_called_with(
            config_mock,
            code_dir,
            artifacts_dir,
            scratch_dir,
            manifest_path,
            runtime,
            architecture,
            None,
            None,
            True,
            True,
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_process_with_metadata(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        runtime = "runtime"
        packagetype = ZIP
        architecture = ARM64
        scratch_dir = "scratch"
        handler = "handler.handle"
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_in_process = Mock()

        code_dir = str(Path("/base/dir/path/to/source").resolve())
        artifacts_dir = str(Path("/build/dir/function_full_path"))
        manifest_path = str(Path(os.path.join(code_dir, config_mock.manifest_name)).resolve())

        self.builder._build_function(
            function_name,
            codeuri,
            packagetype,
            runtime,
            architecture,
            handler,
            artifacts_dir,
            metadata={"BuildMethod": "Workflow"},
        )

        get_workflow_config_mock.assert_called_with(
            runtime, code_dir, self.builder._base_dir, specified_workflow="Workflow"
        )

        self.builder._build_function_in_process.assert_called_with(
            config_mock,
            code_dir,
            artifacts_dir,
            scratch_dir,
            manifest_path,
            runtime,
            architecture,
            None,
            None,
            True,
            True,
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_container(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        runtime = "runtime"
        packagetype = ZIP
        architecture = ARM64
        scratch_dir = "scratch"
        handler = "handler.handle"
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_on_container = Mock()

        code_dir = str(Path("/base/dir/path/to/source").resolve())
        artifacts_dir = str(Path("/build/dir/function_full_path"))
        manifest_path = str(Path(os.path.join(code_dir, config_mock.manifest_name)).resolve())

        # Settting the container manager will make us use the container
        self.builder._container_manager = Mock()
        self.builder._build_function(function_name, codeuri, packagetype, runtime, architecture, handler, artifacts_dir)

        self.builder._build_function_on_container.assert_called_with(
            config_mock, code_dir, artifacts_dir, manifest_path, runtime, architecture, None, None, None
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_container_with_env_vars(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        runtime = "runtime"
        packagetype = ZIP
        scratch_dir = "scratch"
        handler = "handler.handle"
        architecture = ARM64
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"
        env_vars = {"TEST": "test"}

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_on_container = Mock()

        code_dir = str(Path("/base/dir/path/to/source").resolve())
        artifacts_dir = str(Path("/build/dir/function_name"))
        manifest_path = str(Path(os.path.join(code_dir, config_mock.manifest_name)).resolve())

        # Settting the container manager will make us use the container
        self.builder._container_manager = Mock()
        self.builder._build_function(
            function_name,
            codeuri,
            packagetype,
            runtime,
            architecture,
            handler,
            artifacts_dir,
            container_env_vars=env_vars,
        )

        self.builder._build_function_on_container.assert_called_with(
            config_mock, code_dir, artifacts_dir, manifest_path, runtime, architecture, None, {"TEST": "test"}, None
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_container_with_custom_specified_build_image(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        runtime = "runtime"
        packagetype = ZIP
        scratch_dir = "scratch"
        handler = "handler.handle"
        image_uri = "image uri"
        build_images = {function_name: image_uri}
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"
        architecture = ARM64

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_on_container = Mock()

        code_dir = str(Path("/base/dir/path/to/source").resolve())
        artifacts_dir = str(Path("/build/dir/function_name"))
        manifest_path = str(Path(os.path.join(code_dir, config_mock.manifest_name)).resolve())

        # Settting the container manager will make us use the container
        self.builder._container_manager = Mock()
        self.builder._build_images = build_images
        self.builder._build_function(
            function_name, codeuri, packagetype, runtime, architecture, handler, artifacts_dir, container_env_vars=None
        )

        self.builder._build_function_on_container.assert_called_with(
            config_mock, code_dir, artifacts_dir, manifest_path, runtime, architecture, None, None, image_uri
        )

    @patch("samcli.lib.build.app_builder.get_workflow_config")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_container_with_custom_default_build_image(self, osutils_mock, get_workflow_config_mock):
        function_name = "function_name"
        codeuri = "path/to/source"
        runtime = "runtime"
        packagetype = ZIP
        scratch_dir = "scratch"
        handler = "handler.handle"
        image_uri = "image uri"
        build_images = {"abc": "efg", None: image_uri}
        config_mock = get_workflow_config_mock.return_value = Mock()
        config_mock.manifest_name = "manifest_name"
        architecture = ARM64

        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=scratch_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()

        self.builder._build_function_on_container = Mock()

        code_dir = str(Path("/base/dir/path/to/source").resolve())
        artifacts_dir = str(Path("/build/dir/function_name"))
        manifest_path = str(Path(os.path.join(code_dir, config_mock.manifest_name)).resolve())

        # Settting the container manager will make us use the container
        self.builder._container_manager = Mock()
        self.builder._build_images = build_images
        self.builder._build_function(
            function_name, codeuri, packagetype, runtime, architecture, handler, artifacts_dir, container_env_vars=None
        )

        self.builder._build_function_on_container.assert_called_with(
            config_mock, code_dir, artifacts_dir, manifest_path, runtime, architecture, None, None, image_uri
        )


class TestApplicationBuilder_build_function_in_process(TestCase):
    def setUp(self):
        self.builder = ApplicationBuilder(
            Mock(), "/build/dir", "/base/dir", "/cache/dir", mode="mode", stream_writer=StreamWriter(sys.stderr)
        )

    @patch("samcli.lib.build.app_builder.LambdaBuilder")
    def test_must_use_lambda_builder(self, lambda_builder_mock):
        config_mock = Mock()
        builder_instance_mock = lambda_builder_mock.return_value = Mock()

        result = self.builder._build_function_in_process(
            config_mock,
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            "runtime",
            X86_64,
            None,
            None,
            True,
            True,
        )
        self.assertEqual(result, "artifacts_dir")

        lambda_builder_mock.assert_called_with(
            language=config_mock.language,
            dependency_manager=config_mock.dependency_manager,
            application_framework=config_mock.application_framework,
        )

        builder_instance_mock.build.assert_called_with(
            "source_dir",
            "artifacts_dir",
            "scratch_dir",
            "manifest_path",
            runtime="runtime",
            executable_search_paths=config_mock.executable_search_paths,
            mode="mode",
            options=None,
            architecture=X86_64,
            dependencies_dir=None,
            download_dependencies=True,
            combine_dependencies=True,
        )

    @patch("samcli.lib.build.app_builder.LambdaBuilder")
    def test_must_raise_on_error(self, lambda_builder_mock):
        config_mock = Mock()
        builder_instance_mock = lambda_builder_mock.return_value = Mock()
        builder_instance_mock.build.side_effect = LambdaBuilderError()
        self.builder._get_build_options = Mock(return_value=None)

        with self.assertRaises(BuildError):
            self.builder._build_function_in_process(
                config_mock,
                "source_dir",
                "artifacts_dir",
                "scratch_dir",
                "manifest_path",
                "runtime",
                X86_64,
                None,
                None,
                True,
                True,
            )


class TestApplicationBuilder_build_function_on_container(TestCase):
    def setUp(self):
        self.container_manager = Mock()
        self.builder = ApplicationBuilder(
            Mock(),
            "/build/dir",
            "/base/dir",
            "/cache/dir",
            container_manager=self.container_manager,
            mode="mode",
            stream_writer=StreamWriter(sys.stderr),
        )
        self.builder._parse_builder_response = Mock()

    @patch("samcli.lib.build.app_builder.LambdaBuildContainer")
    @patch("samcli.lib.build.app_builder.lambda_builders_protocol_version")
    @patch("samcli.lib.build.app_builder.LOG")
    @patch("samcli.lib.build.app_builder.osutils")
    def test_must_build_in_container(self, osutils_mock, LOGMock, protocol_version_mock, LambdaBuildContainerMock):
        config = Mock()
        log_level = LOGMock.getEffectiveLevel.return_value = "foo"
        stdout_data = "container stdout response data"
        response = {"result": {"artifacts_dir": "/some/dir"}}

        def mock_wait_for_logs(stdout, stderr):
            stdout.write(stdout_data.encode("utf-8"))

        # Wire all mocks correctly
        container_mock = LambdaBuildContainerMock.return_value = Mock()
        container_mock.wait_for_logs = mock_wait_for_logs
        self.builder._parse_builder_response.return_value = response

        result = self.builder._build_function_on_container(
            config, "source_dir", "artifacts_dir", "manifest_path", "runtime", X86_64, None
        )
        self.assertEqual(result, "artifacts_dir")

        LambdaBuildContainerMock.assert_called_once_with(
            protocol_version_mock,
            config.language,
            config.dependency_manager,
            config.application_framework,
            "source_dir",
            "manifest_path",
            "runtime",
            X86_64,
            image=None,
            log_level=log_level,
            optimizations=None,
            options=None,
            executable_search_paths=config.executable_search_paths,
            mode="mode",
            env_vars={},
        )

        self.container_manager.run.assert_called_with(container_mock)
        self.builder._parse_builder_response.assert_called_once_with(stdout_data, container_mock.image)
        container_mock.copy.assert_called_with(response["result"]["artifacts_dir"] + "/.", "artifacts_dir")
        self.container_manager.stop.assert_called_with(container_mock)

    @patch("samcli.lib.build.app_builder.LambdaBuildContainer")
    def test_must_raise_on_unsupported_container(self, LambdaBuildContainerMock):
        config = Mock()

        container_mock = LambdaBuildContainerMock.return_value = Mock()
        container_mock.image = "image name"
        container_mock.executable_name = "myexecutable"

        self.container_manager.run.side_effect = docker.errors.APIError(
            "Bad Request: 'lambda-builders' " "executable file not found in $PATH"
        )

        with self.assertRaises(UnsupportedBuilderLibraryVersionError) as ctx:
            self.builder._build_function_on_container(
                config, "source_dir", "artifacts_dir", "scratch_dir", "manifest_path", "runtime", X86_64, {}
            )

        msg = (
            "You are running an outdated version of Docker container 'image name' that is not compatible with"
            "this version of SAM CLI. Please upgrade to continue to continue with build. "
            "Reason: 'myexecutable executable not found in container'"
        )

        self.assertEqual(str(ctx.exception), msg)
        self.container_manager.stop.assert_called_with(container_mock)

    def test_must_raise_on_docker_not_running(self):
        config = Mock()

        self.container_manager.is_docker_reachable = False

        with self.assertRaises(BuildInsideContainerError) as ctx:
            self.builder._build_function_on_container(
                config, "source_dir", "artifacts_dir", "scratch_dir", "manifest_path", "runtime", X86_64, {}
            )

        self.assertEqual(
            str(ctx.exception), "Docker is unreachable. Docker needs to be running to build inside a container."
        )

    @patch("samcli.lib.build.app_builder.supports_build_in_container")
    def test_must_raise_on_unsupported_container_build(self, supports_build_in_container_mock):
        config = Mock()

        reason = "my reason"
        supports_build_in_container_mock.return_value = (False, reason)

        with self.assertRaises(ContainerBuildNotSupported) as ctx:
            self.builder._build_function_on_container(
                config, "source_dir", "artifacts_dir", "scratch_dir", "manifest_path", "runtime", X86_64, {}
            )

        self.assertEqual(str(ctx.exception), reason)


class TestApplicationBuilder_parse_builder_response(TestCase):
    def setUp(self):
        self.image_name = "name"
        self.builder = ApplicationBuilder(
            Mock(), "/build/dir", "/base/dir", "/cache/dir", stream_writer=StreamWriter(sys.stderr)
        )

    def test_must_parse_json(self):
        data = {"valid": "json"}

        result = self.builder._parse_builder_response(json.dumps(data), self.image_name)
        self.assertEqual(result, data)

    def test_must_fail_on_invalid_json(self):
        data = "{invalid: json}"

        with self.assertRaises(ValueError):
            self.builder._parse_builder_response(data, self.image_name)

    def test_must_raise_on_user_error(self):
        msg = "invalid params"
        data = {"error": {"code": 488, "message": msg}}

        with self.assertRaises(BuildInsideContainerError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        self.assertEqual(str(ctx.exception), msg)

    def test_must_raise_on_version_mismatch(self):
        msg = "invalid params"
        data = {"error": {"code": 505, "message": msg}}

        with self.assertRaises(UnsupportedBuilderLibraryVersionError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        expected = str(UnsupportedBuilderLibraryVersionError(self.image_name, msg))
        self.assertEqual(str(ctx.exception), expected)

    def test_must_raise_on_method_not_found(self):
        msg = "invalid method"
        data = {"error": {"code": -32601, "message": msg}}

        with self.assertRaises(UnsupportedBuilderLibraryVersionError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        expected = str(UnsupportedBuilderLibraryVersionError(self.image_name, msg))
        self.assertEqual(str(ctx.exception), expected)

    def test_must_raise_on_all_other_codes(self):
        msg = "builder crashed"
        data = {"error": {"code": 1, "message": msg}}

        with self.assertRaises(ValueError) as ctx:
            self.builder._parse_builder_response(json.dumps(data), self.image_name)

        self.assertEqual(str(ctx.exception), msg)


class TestApplicationBuilder_make_env_vars(TestCase):
    def test_make_env_vars_with_env_file(self):
        function1 = generate_function(name="Function1")
        file_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR2": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = ApplicationBuilder._make_env_vars(function1, file_env_vars, {})
        self.assertEqual(result, {"ENV_VAR1": "1", "ENV_VAR2": "2"})

    def test_make_env_vars_with_function_precedence(self):
        function1 = generate_function(name="Function1")
        file_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR1": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = ApplicationBuilder._make_env_vars(function1, file_env_vars, {})
        self.assertEqual(result, {"ENV_VAR1": "2"})

    def test_make_env_vars_with_inline_env(self):
        function1 = generate_function(name="Function1")
        inline_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR2": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = ApplicationBuilder._make_env_vars(function1, {}, inline_env_vars)
        self.assertEqual(result, {"ENV_VAR1": "1", "ENV_VAR2": "2"})

    def test_make_env_vars_with_both(self):
        function1 = generate_function(name="Function1")
        file_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR2": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        inline_env_vars = {
            "Parameters": {"ENV_VAR1": "2"},
            "Function1": {"ENV_VAR2": "3"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = ApplicationBuilder._make_env_vars(function1, file_env_vars, inline_env_vars)
        self.assertEqual(result, {"ENV_VAR1": "2", "ENV_VAR2": "3"})
