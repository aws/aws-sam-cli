import os
from unittest import TestCase
from unittest.mock import Mock, patch, mock_open, ANY

from samcli.lib.bootstrap.nested_stack.nested_stack_manager import generate_auto_dependency_layer_stack, \
    NESTED_STACK_NAME
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
        result = generate_auto_dependency_layer_stack(
            self.stack_name,
            self.build_dir,
            self.stack_location,
            template,
            app_build_result
        )

        self.assertEqual(template, result)

    def test_unsupported_resource(self):
        template = {
            "Resources": {
                "MySqsQueue": {
                    "Type": AWS_SQS_QUEUE
                }
            }
        }
        app_build_result = ApplicationBuildResult(Mock(), {})
        result = generate_auto_dependency_layer_stack(
            self.stack_name,
            self.build_dir,
            self.stack_location,
            template,
            app_build_result
        )

        self.assertEqual(template, result)

    def test_image_function(self):
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {
                        "Runtime": "unsupported_runtime",
                        "PackageType": "IMAGE"
                    }
                }
            }
        }
        app_build_result = ApplicationBuildResult(Mock(), {
            "MyFunction": "path/to/build/dir"
        })
        result = generate_auto_dependency_layer_stack(
            self.stack_name,
            self.build_dir,
            self.stack_location,
            template,
            app_build_result
        )

        self.assertEqual(template, result)

    def test_unsupported_runtime(self):
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {
                        "Runtime": "unsupported_runtime"
                    }
                }
            }
        }
        app_build_result = ApplicationBuildResult(Mock(), {
            "MyFunction": "path/to/build/dir"
        })
        result = generate_auto_dependency_layer_stack(
            self.stack_name,
            self.build_dir,
            self.stack_location,
            template,
            app_build_result
        )

        self.assertEqual(template, result)


    def test_no_dependencies_dir(self):
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {
                        "Runtime": "python3.8"
                    }
                }
            }
        }
        build_graph = Mock()
        build_graph.get_function_build_definitions.return_value = []
        app_build_result = ApplicationBuildResult(build_graph, {
            "MyFunction": "path/to/build/dir"
        })
        result = generate_auto_dependency_layer_stack(
            self.stack_name,
            self.build_dir,
            self.stack_location,
            template,
            app_build_result
        )

        self.assertEqual(template, result)

    @patch("samcli.lib.bootstrap.nested_stack.nested_stack_manager.move_template")
    def test_with_zip_function(self, patched_move_template):
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {
                        "Runtime": "python3.8"
                    }
                }
            }
        }

        with osutils.mkdir_temp() as tmp_dir:
            # prepare build graph
            dependencies_dir = tmp_dir
            function = Mock()
            function.name = "MyFunction"
            functions = [function]
            build_graph = Mock()
            function_definition_mock = Mock(dependencies_dir=dependencies_dir, functions=functions)
            build_graph.get_function_build_definitions.return_value = [function_definition_mock]
            app_build_result = ApplicationBuildResult(build_graph, {
                "MyFunction": "path/to/build/dir"
            })

            result = generate_auto_dependency_layer_stack(
                self.stack_name,
                self.build_dir,
                self.stack_location,
                template,
                app_build_result
            )

            patched_move_template.assert_called_with(self.stack_location, os.path.join(self.build_dir, "nested_template.yaml"), ANY)
            self.assertNotEqual(template, result)

            resources = result.get("Resources")
            self.assertIn(NESTED_STACK_NAME, resources.keys())

            self.assertTrue(resources.get("MyFunction", {}).get("Properties", {}).get("Layers", []))


