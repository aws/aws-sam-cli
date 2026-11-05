from pathlib import Path
from unittest import TestCase, skipIf
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.lib.build.bundler import EsbuildBundlerManager
from samcli.lib.providers.provider import Stack
from tests.testing_utils import IS_WINDOWS
from tests.unit.commands.buildcmd.test_build_context import DummyStack


class EsbuildBundler_is_node_option_set(TestCase):
    @parameterized.expand(
        [
            (
                {"Properties": {"Environment": {"Variables": {"NODE_OPTIONS": "--enable-source-maps"}}}},
                True,
            ),
            (
                {"Properties": {"Environment": {"Variables": {"NODE_OPTIONS": "nothing"}}}},
                False,
            ),
        ]
    )
    def test_is_node_option_set(self, resource, expected_result):
        esbuild_bundler_manager = EsbuildBundlerManager(Mock())
        self.assertEqual(esbuild_bundler_manager._is_node_option_set(resource), expected_result)

    def test_enable_source_map_missing(self):
        esbuild_bundler_manager = EsbuildBundlerManager(Mock())
        self.assertFalse(esbuild_bundler_manager._is_node_option_set({"Properties": {}}))


class EsbuildBundler_enable_source_maps(TestCase):
    @parameterized.expand(
        [
            (
                {
                    "Resources": {
                        "test": {"Metadata": {"BuildMethod": "esbuild", "BuildProperties": {"Sourcemap": True}}}
                    }
                },
            ),
            (
                {
                    "Resources": {
                        "test": {
                            "Properties": {"Environment": {"Variables": {"NODE_OPTIONS": "--something"}}},
                            "Metadata": {"BuildMethod": "esbuild", "BuildProperties": {"Sourcemap": True}},
                        }
                    }
                },
            ),
        ]
    )
    def test_enable_source_maps_only_source_map(self, template):
        esbuild_manager = EsbuildBundlerManager(stack=DummyStack(template.get("Resources")), template=template)

        updated_template = esbuild_manager._set_sourcemap_env_from_metadata(template)

        for _, resource in updated_template["Resources"].items():
            self.assertIn("--enable-source-maps", resource["Properties"]["Environment"]["Variables"]["NODE_OPTIONS"])

    @parameterized.expand(
        [
            ({"Resources": {"test": {"Metadata": {"BuildMethod": "esbuild"}}}}, True),
            (
                {
                    "Resources": {
                        "test": {
                            "Properties": {"Environment": {"Variables": {"NODE_OPTIONS": "--enable-source-maps"}}},
                            "Metadata": {"BuildMethod": "esbuild"},
                        }
                    }
                },
                True,
            ),
            (
                {
                    "Resources": {
                        "test": {
                            "Metadata": {"BuildMethod": "esbuild", "BuildProperties": {"Sourcemap": False}},
                        }
                    }
                },
                False,
            ),
            (
                {
                    "Globals": {"Environment": {"Variables": {"NODE_OPTIONS": "--enable-source-maps"}}},
                    "Resources": {
                        "test": {
                            "Properties": {},
                            "Metadata": {"BuildMethod": "esbuild"},
                        }
                    },
                },
                True,
            ),
        ]
    )
    def test_enable_source_maps_only_node_options(
        self,
        template,
        expected_value,
    ):
        esbuild_manager = EsbuildBundlerManager(stack=DummyStack(template.get("Resources")), template=template)
        esbuild_manager._is_node_option_set = Mock()
        esbuild_manager._is_node_option_set.return_value = True
        updated_template = esbuild_manager.set_sourcemap_metadata_from_env()

        for _, resource in updated_template.resources.items():
            self.assertEqual(resource["Metadata"]["BuildProperties"]["Sourcemap"], expected_value)

    def test_warnings_printed(self):
        template = {
            "Resources": {
                "test": {
                    "Properties": {
                        "Environment": {"Variables": {"NODE_OPTIONS": ["--something"]}},
                    },
                    "Metadata": {"BuildMethod": "esbuild", "BuildProperties": {"Sourcemap": True}},
                }
            }
        }
        esbuild_manager = EsbuildBundlerManager(stack=DummyStack(template.get("Resources")), template=template)
        esbuild_manager._warn_using_source_maps = Mock()
        esbuild_manager._warn_invalid_node_options = Mock()
        esbuild_manager._set_sourcemap_env_from_metadata(template)

        esbuild_manager._warn_using_source_maps.assert_called()
        esbuild_manager._warn_invalid_node_options.assert_called()


class EsbuildBundler_esbuild_configured(TestCase):
    @parameterized.expand(
        [
            (
                {
                    "test": {
                        "Properties": {
                            "Environment": {"Variables": {"NODE_OPTIONS": ["--something"]}},
                            "Handler": "FakeHandler",
                        },
                        "Metadata": {"BuildMethod": "esbuild", "BuildProperties": {"Sourcemap": True}},
                        "Type": "AWS::Serverless::Function",
                    }
                },
                True,
            ),
            (
                {
                    "test": {
                        "Properties": {
                            "Environment": {"Variables": {"NODE_OPTIONS": ["--something"]}},
                            "Handler": "FakeHandler",
                        },
                        "Metadata": {"BuildMethod": "Makefile", "BuildProperties": {"Sourcemap": True}},
                        "Type": "AWS::Serverless::Function",
                    }
                },
                False,
            ),
        ],
    )
    def test_detects_if_esbuild_is_configured(self, stack_resources, expected):
        stack = DummyStack(stack_resources)
        stack.stack_path = "/path"
        stack.location = "/location"
        esbuild_manager = EsbuildBundlerManager(stack)
        self.assertEqual(esbuild_manager.esbuild_configured(), expected)

    @patch("samcli.lib.build.bundler.SamWebFunctionProvider")
    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider.__init__", return_value=None)
    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider.get_all", return_value={})
    def test_use_raw_codeuri_passed(self, get_all_mock, provider_mock, web_provider_mock):
        web_provider_mock.return_value.get_all.return_value = []
        EsbuildBundlerManager([]).esbuild_configured()
        provider_mock.assert_called_with([[]], use_raw_codeuri=True, ignore_code_extraction_warnings=True)


class PostProcessHandler(TestCase):
    def test_get_path_and_filename_from_handler(self):
        handler = "src/functions/FunctionName/app.Handler"
        file = EsbuildBundlerManager._get_path_and_filename_from_handler(handler)
        expected_path = (Path("src") / "functions" / "FunctionName" / "app.js").as_posix()
        self.assertEqual(file, expected_path)

    @patch("samcli.lib.build.bundler.Path.is_file")
    def test_check_invalid_lambda_handler(self, mock_is_file):
        mock_is_file.return_value = False
        bundler_manager = EsbuildBundlerManager(Mock(), build_dir="/build/dir")
        bundler_manager._get_path_and_filename_from_handler = Mock()
        bundler_manager._get_path_and_filename_from_handler.return_value = "some-path"
        return_val = bundler_manager._should_update_handler("", "")
        self.assertTrue(return_val)

    def test_check_invalid_lambda_handler_none_build_dir(self):
        bundler_manager = EsbuildBundlerManager(Mock(), build_dir=None)
        return_val = bundler_manager._should_update_handler("", "")
        self.assertFalse(return_val)

    def test_should_not_update_layer_path(self):
        bundler_manager = EsbuildBundlerManager(Mock(), build_dir="/build/dir")
        bundler_manager._get_path_and_filename_from_handler = Mock()
        bundler_manager._get_path_and_filename_from_handler.return_value = "/opt/nodejs/node_modules/d/handler.handler"
        return_val = bundler_manager._should_update_handler("", "")
        self.assertFalse(return_val)

    def test_update_function_handler(self):
        resources = {
            "FunctionA": {
                "Properties": {
                    "Handler": "functions/source/create/app.handler",
                },
                "Metadata": {"BuildMethod": "esbuild"},
                "Type": "AWS::Serverless::Function",
            },
            "FunctionB": {
                "Properties": {
                    "Handler": "functions/source/delete/app.handler",
                },
                "Metadata": {"BuildMethod": "esbuild"},
                "Type": "AWS::Serverless::Function",
            },
            "FunctionC": {
                "Properties": {
                    "Handler": "functions/source/update/app.handler",
                },
                "Type": "AWS::Serverless::Function",
            },
        }

        template = {"Resources": resources}

        dummy_stack = DummyStack(resources)

        bundler_manager = EsbuildBundlerManager(dummy_stack, build_dir="build/dir")
        bundler_manager._check_invalid_lambda_handler = Mock()
        bundler_manager._check_invalid_lambda_handler.return_value = True
        updated_template = bundler_manager._update_function_handler(template)
        updated_handler_a = updated_template.get("Resources").get("FunctionA").get("Properties").get("Handler")
        updated_handler_b = updated_template.get("Resources").get("FunctionB").get("Properties").get("Handler")
        updated_handler_c = updated_template.get("Resources").get("FunctionC").get("Properties").get("Handler")
        self.assertEqual(updated_handler_a, "app.handler")
        self.assertEqual(updated_handler_b, "app.handler")
        self.assertEqual(updated_handler_c, "functions/source/update/app.handler")

    @parameterized.expand(
        [("/opt/my/path/handler.handler", "/opt/my/path/handler.js"), ("handler.handler", "handler.js")]
    )
    def test_get_handler_path_unix(self, input_path, expected_path):
        result_path = EsbuildBundlerManager(Mock())._get_path_and_filename_from_handler(input_path)

        self.assertEqual(result_path, expected_path)

    @parameterized.expand(
        [
            ("\\opt\\my\\path\\handler.handler", "/opt/my/path/handler.js"),
        ]
    )
    @skipIf(not IS_WINDOWS, "Skipping POSIX converting logic since WindowsPath is not available on unix systems")
    def test_get_handler_windows_returns_posix(self, input_path, expected_path):
        result_path = EsbuildBundlerManager(Mock())._get_path_and_filename_from_handler(input_path)

        self.assertEqual(result_path, expected_path)


class EsbuildBundlerWebFunctions(TestCase):
    def _stack(self, properties, metadata=None):
        resource = {"Type": "AWS::Serverless::WebFunction", "Properties": properties}
        resource["Metadata"] = metadata if metadata is not None else {"BuildMethod": "esbuild"}
        return Stack("", "", "template.yaml", {}, {"Resources": {"WebFn": resource}})

    def test_esbuild_configured_for_web_functions(self):
        self.assertTrue(
            EsbuildBundlerManager(self._stack({"Runtime": "nodejs24.x", "CodeUri": "web"})).esbuild_configured()
        )
        self.assertFalse(
            EsbuildBundlerManager(self._stack({"Runtime": "nodejs24.x", "CodeUri": "web"}, {})).esbuild_configured()
        )

    @patch("samcli.lib.build.bundler.Path.is_file", return_value=False)
    def test_entry_point_points_at_the_bundled_file(self, _):
        stack = self._stack({"Runtime": "nodejs24.x", "CodeUri": "web", "EntryPoint": "src/server.ts"})
        template = {"Resources": {"WebFn": {"Properties": {"EntryPoint": "src/server.ts"}}}}
        processed = EsbuildBundlerManager(stack, template, "build").handle_template_post_processing()
        self.assertEqual(processed["Resources"]["WebFn"]["Properties"]["EntryPoint"], "server.js")

    @parameterized.expand(
        [
            ("./server.ts", "server.js"),
            ("src/v1.2/server.ts", "server.js"),
            ("server.config.ts", "server.config.js"),
        ]
    )
    @patch("samcli.lib.build.bundler.Path.is_file", return_value=False)
    def test_dotted_entry_point_points_at_the_bundled_file(self, entry_point, expected, _):
        stack = self._stack({"Runtime": "nodejs24.x", "CodeUri": "web", "EntryPoint": entry_point})
        template = {"Resources": {"WebFn": {"Properties": {"EntryPoint": entry_point}}}}
        processed = EsbuildBundlerManager(stack, template, "build").handle_template_post_processing()
        self.assertEqual(processed["Resources"]["WebFn"]["Properties"]["EntryPoint"], expected)

    @patch("samcli.lib.build.bundler.Path.is_file", return_value=True)
    def test_entry_point_that_exists_in_the_artifact_is_kept(self, _):
        stack = self._stack({"Runtime": "nodejs24.x", "CodeUri": "web", "EntryPoint": "server.js"})
        template = {"Resources": {"WebFn": {"Properties": {"EntryPoint": "server.js"}}}}
        processed = EsbuildBundlerManager(stack, template, "build").handle_template_post_processing()
        self.assertEqual(processed["Resources"]["WebFn"]["Properties"]["EntryPoint"], "server.js")

    def test_sourcemap_sets_node_options_in_environment_variables(self):
        stack = self._stack(
            {"Runtime": "nodejs24.x", "CodeUri": "web"},
            {"BuildMethod": "esbuild", "BuildProperties": {"Sourcemap": True}},
        )
        template = {"Resources": {"WebFn": {"Properties": {"EnvironmentVariables": {"A": "b"}}}}}
        processed = EsbuildBundlerManager(stack, template).handle_template_post_processing()
        variables = processed["Resources"]["WebFn"]["Properties"]["EnvironmentVariables"]
        self.assertIn("--enable-source-maps", variables["NODE_OPTIONS"])
        self.assertEqual(variables["A"], "b")
        self.assertNotIn("Environment", processed["Resources"]["WebFn"]["Properties"])

    def test_node_options_in_web_function_environment_variables_are_detected(self):
        resource = {
            "Type": "AWS::Serverless::WebFunction",
            "Properties": {"EnvironmentVariables": {"NODE_OPTIONS": "--enable-source-maps"}},
        }
        self.assertTrue(EsbuildBundlerManager._is_node_option_set(resource))
