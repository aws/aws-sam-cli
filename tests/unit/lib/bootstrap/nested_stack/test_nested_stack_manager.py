import os
from unittest import TestCase
from unittest.mock import Mock, patch, ANY, call

from samcli.lib.bootstrap.nested_stack.nested_stack_manager import (
    NESTED_STACK_NAME, NestedStackManager,
)
from samcli.lib.build.app_builder import ApplicationBuildResult
from samcli.lib.utils import osutils
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

    def test_no_dependencies_dir(self):
        template = {
            "Resources": {"MyFunction": {"Type": AWS_SERVERLESS_FUNCTION, "Properties": {"Runtime": "python3.8"}}}
        }
        build_graph = Mock()
        build_graph.get_function_build_definitions.return_value = []
        app_build_result = ApplicationBuildResult(build_graph, {"MyFunction": "path/to/build/dir"})
        nested_stack_manager = NestedStackManager(
            self.stack_name, self.build_dir, self.stack_location, template, app_build_result
        )
        result = nested_stack_manager.generate_auto_dependency_layer_stack()

        self.assertEqual(template, result)

    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.move_template")
    def test_with_zip_function(self, patched_move_template):
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
        build_graph.get_function_build_definitions.return_value = [function_definition_mock]
        app_build_result = ApplicationBuildResult(build_graph, {"MyFunction": "path/to/build/dir"})

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
            patched_open.assert_has_calls([
                call(os.path.join(dependencies_dir, "AWS_SAM_CLI_README"), "w+"),
                call().__enter__().write(
                    f"This layer contains dependencies of function {function_name} and automatically added by AWS SAM CLI command 'sam sync'")
            ], any_order=True)
