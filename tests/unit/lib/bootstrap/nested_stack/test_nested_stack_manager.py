import os
from unittest import TestCase
from unittest.mock import Mock, patch, ANY, call

from parameterized import parameterized

from samcli.lib.bootstrap.nested_stack.nested_stack_manager import (
    NESTED_STACK_NAME,
    NestedStackManager,
)
from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.sync.exceptions import InvalidRuntimeDefinitionForFunction
from samcli.lib.utils.osutils import BUILD_DIR_PERMISSIONS
from samcli.lib.utils.resources import AWS_SQS_QUEUE, AWS_SERVERLESS_FUNCTION


class TestNestedStackManager(TestCase):
    def setUp(self) -> None:
        self.stack_name = "stack_name"
        self.build_dir = "build_dir"
        self.stack_location = "stack_location"

    def test_nothing_to_add(self):
        template = {}
        app_build_result = ApplicationBuildResult(Mock(), {})
        nested_stack_manager = NestedStackManager(
            self.stack_name, self.build_dir, self.stack_location, template, app_build_result
        )
        result = nested_stack_manager.generate_auto_dependency_layer_stack()

        self.assertEqual(template, result)

    def test_unsupported_resource(self):
        template = {"Resources": {"MySqsQueue": {"Type": AWS_SQS_QUEUE}}}
        app_build_result = ApplicationBuildResult(Mock(), {})
        nested_stack_manager = NestedStackManager(
            self.stack_name, self.build_dir, self.stack_location, template, app_build_result
        )
        result = nested_stack_manager.generate_auto_dependency_layer_stack()

        self.assertEqual(template, result)

    def test_image_function(self):
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {"Runtime": "unsupported_runtime", "PackageType": "IMAGE"},
                }
            }
        }
        app_build_result = ApplicationBuildResult(Mock(), {"MyFunction": "path/to/build/dir"})
        nested_stack_manager = NestedStackManager(
            self.stack_name, self.build_dir, self.stack_location, template, app_build_result
        )
        result = nested_stack_manager.generate_auto_dependency_layer_stack()

        self.assertEqual(template, result)

    def test_unsupported_runtime(self):
        template = {
            "Resources": {
                "MyFunction": {"Type": AWS_SERVERLESS_FUNCTION, "Properties": {"Runtime": "unsupported_runtime"}}
            }
        }
        app_build_result = ApplicationBuildResult(Mock(), {"MyFunction": "path/to/build/dir"})
        nested_stack_manager = NestedStackManager(
            self.stack_name, self.build_dir, self.stack_location, template, app_build_result
        )
        result = nested_stack_manager.generate_auto_dependency_layer_stack()

        self.assertEqual(template, result)

    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.osutils")
    def test_no_dependencies_dir(self, patched_osutils):
        template = {
            "Resources": {"MyFunction": {"Type": AWS_SERVERLESS_FUNCTION, "Properties": {"Runtime": "python3.8"}}}
        }
        build_graph = Mock()
        build_graph.get_function_build_definition_with_full_path.return_value = None
        app_build_result = ApplicationBuildResult(build_graph, {"MyFunction": "path/to/build/dir"})
        nested_stack_manager = NestedStackManager(
            self.stack_name, self.build_dir, self.stack_location, template, app_build_result
        )
        result = nested_stack_manager.generate_auto_dependency_layer_stack()

        self.assertEqual(template, result)

    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.move_template")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.osutils")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.os.path.isdir")
    def test_with_zip_function(self, patched_isdir, patched_osutils, patched_move_template):
        template = {
            "Resources": {"MyFunction": {"Type": AWS_SERVERLESS_FUNCTION, "Properties": {"Runtime": "python3.8"}}}
        }

        # prepare build graph
        dependencies_dir = Mock()
        function = Mock()
        function.name = "MyFunction"
        functions = [function]
        build_graph = Mock()
        function_definition_mock = Mock(dependencies_dir=dependencies_dir, functions=functions)
        build_graph.get_function_build_definition_with_logical_id.return_value = function_definition_mock
        app_build_result = ApplicationBuildResult(build_graph, {"MyFunction": "path/to/build/dir"})
        patched_isdir.return_value = True

        nested_stack_manager = NestedStackManager(
            self.stack_name, self.build_dir, self.stack_location, template, app_build_result
        )

        with patch.object(nested_stack_manager, "_add_layer_readme_info") as patched_add_readme:
            result = nested_stack_manager.generate_auto_dependency_layer_stack()

            patched_move_template.assert_called_with(
                self.stack_location, os.path.join(self.build_dir, "nested_template.yaml"), ANY
            )
            self.assertNotEqual(template, result)

            resources = result.get("Resources")
            self.assertIn(NESTED_STACK_NAME, resources.keys())

            self.assertTrue(resources.get("MyFunction", {}).get("Properties", {}).get("Layers", []))

    def test_adding_readme_file(self):
        with patch("builtins.open") as patched_open:
            dependencies_dir = "dependencies"
            function_name = "function_name"
            NestedStackManager._add_layer_readme_info(dependencies_dir, function_name)
            patched_open.assert_has_calls(
                [
                    call(os.path.join(dependencies_dir, "AWS_SAM_CLI_README"), "w+"),
                    call()
                    .__enter__()
                    .write(
                        f"This layer contains dependencies of function {function_name} and automatically added by AWS SAM CLI command 'sam sync'"
                    ),
                ],
                any_order=True,
            )

    def test_update_layer_folder_raise_exception_with_no_runtime(self):
        with self.assertRaises(InvalidRuntimeDefinitionForFunction):
            NestedStackManager.update_layer_folder(Mock(), Mock(), Mock(), Mock(), None)

    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.Path")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.shutil")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.osutils")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.NestedStackManager._add_layer_readme_info")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.os.path.isdir")
    def test_update_layer_folder(
        self, patched_isdir, patched_add_layer_readme, patched_osutils, patched_shutil, patched_path
    ):
        build_dir = "build_dir"
        dependencies_dir = "dependencies_dir"
        layer_logical_id = "layer_logical_id"
        function_logical_id = "function_logical_id"
        function_runtime = "python3.9"

        layer_contents_folder = Mock()
        layer_root_folder = Mock()
        layer_root_folder.exists.return_value = True
        layer_root_folder.joinpath.return_value = layer_contents_folder
        patched_path.return_value.joinpath.return_value = layer_root_folder
        patched_isdir.return_value = True

        layer_folder = NestedStackManager.update_layer_folder(
            build_dir, dependencies_dir, layer_logical_id, function_logical_id, function_runtime
        )

        patched_shutil.rmtree.assert_called_with(layer_root_folder)
        layer_contents_folder.mkdir.assert_called_with(BUILD_DIR_PERMISSIONS, parents=True)
        patched_osutils.copytree.assert_called_with(dependencies_dir, str(layer_contents_folder))
        patched_add_layer_readme.assert_called_with(str(layer_root_folder), function_logical_id)
        self.assertEqual(layer_folder, str(layer_root_folder))

    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.Path")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.shutil")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.osutils")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.NestedStackManager._add_layer_readme_info")
    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.os.path.isdir")
    def test_skipping_dependency_copy_when_function_has_no_dependencies(
        self, patched_isdir, patched_add_layer_readme, patched_osutils, patched_shutil, patched_path
    ):
        build_dir = "build_dir"
        dependencies_dir = "dependencies_dir"
        layer_logical_id = "layer_logical_id"
        function_logical_id = "function_logical_id"
        function_runtime = "python3.9"

        layer_contents_folder = Mock()
        layer_root_folder = Mock()
        layer_root_folder.exists.return_value = True
        layer_root_folder.joinpath.return_value = layer_contents_folder
        patched_path.return_value.joinpath.return_value = layer_root_folder

        patched_isdir.return_value = False

        NestedStackManager.update_layer_folder(
            build_dir, dependencies_dir, layer_logical_id, function_logical_id, function_runtime
        )
        patched_osutils.copytree.assert_not_called()

    @parameterized.expand([("python3.8", True), ("ruby2.7", False)])
    def test_is_runtime_supported(self, runtime, supported):
        self.assertEqual(NestedStackManager.is_runtime_supported(runtime), supported)
