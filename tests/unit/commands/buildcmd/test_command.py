import os
import click

from unittest import TestCase
from unittest.mock import Mock, patch, call
from parameterized import parameterized

from samcli.commands.build.command import do_cli, _get_mode_value_from_envvar, _process_env_var, _process_image_options
from samcli.commands.exceptions import UserException
from samcli.lib.build.app_builder import (
    BuildError,
    UnsupportedBuilderLibraryVersionError,
    BuildInsideContainerError,
    ContainerBuildNotSupported,
)
from samcli.lib.build.workflow_config import UnsupportedRuntimeException
from samcli.local.lambdafn.exceptions import FunctionNotFound


class DeepWrap(Exception):
    pass


class TestDoCli(TestCase):
    @patch("samcli.commands.build.build_context.BuildContext")
    @patch("samcli.lib.build.app_builder.ApplicationBuilder")
    @patch("samcli.commands._utils.template.move_template")
    @patch("samcli.commands.build.command.os")
    def test_must_succeed_build(self, os_mock, move_template_mock, ApplicationBuilderMock, BuildContextMock):

        ctx_mock = Mock()

        # create stack mocks
        root_stack = Mock()
        root_stack.is_root_stack = True
        root_stack.get_output_template_path = Mock(return_value="./build_dir/template.yaml")
        child_stack = Mock()
        child_stack.get_output_template_path = Mock(return_value="./build_dir/abcd/template.yaml")
        ctx_mock.stacks = [root_stack, child_stack]
        stack_output_template_path_by_stack_path = {
            root_stack.stack_path: "./build_dir/template.yaml",
            child_stack.stack_path: "./build_dir/abcd/template.yaml",
        }

        BuildContextMock.return_value.__enter__ = Mock()
        BuildContextMock.return_value.__enter__.return_value = ctx_mock
        builder_mock = ApplicationBuilderMock.return_value = Mock()
        artifacts = builder_mock.build.return_value = "artifacts"
        modified_template_root = "modified template 1"
        modified_template_child = "modified template 2"
        builder_mock.update_template.side_effect = [modified_template_root, modified_template_child]

        iac = Mock()
        project = Mock()

        do_cli(
            "function_identifier",
            "template",
            "base_dir",
            "build_dir",
            "cache_dir",
            "clean",
            "use_container",
            "cached",
            "parallel",
            "manifest_path",
            "docker_network",
            "skip_pull",
            "parameter_overrides",
            "mode",
            (""),
            "container_env_var_file",
            (),
            "CFN",
            iac,
            project,
        )

        ApplicationBuilderMock.assert_called_once_with(
            ctx_mock.resources_to_build,
            ctx_mock.build_dir,
            ctx_mock.base_dir,
            ctx_mock.cache_dir,
            ctx_mock.cached,
            ctx_mock.is_building_specific_resource,
            manifest_path_override=ctx_mock.manifest_path_override,
            container_manager=ctx_mock.container_manager,
            mode=ctx_mock.mode,
            parallel="parallel",
            container_env_var={},
            container_env_var_file="container_env_var_file",
            build_images={},
        )
        builder_mock.build.assert_called_once()
        builder_mock.update_template.assert_has_calls(
            [
                call(
                    root_stack,
                    artifacts,
                )
            ],
            [
                call(
                    child_stack,
                    artifacts,
                )
            ],
        )
        iac.write_project.assert_has_calls([call(ctx_mock.project, ctx_mock.build_dir)])

    @parameterized.expand(
        [
            (UnsupportedRuntimeException(), "UnsupportedRuntimeException"),
            (BuildInsideContainerError(), "BuildInsideContainerError"),
            (BuildError(wrapped_from=DeepWrap().__class__.__name__, msg="Test"), "DeepWrap"),
            (ContainerBuildNotSupported(), "ContainerBuildNotSupported"),
            (
                UnsupportedBuilderLibraryVersionError(container_name="name", error_msg="msg"),
                "UnsupportedBuilderLibraryVersionError",
            ),
        ]
    )
    @patch("samcli.commands.build.build_context.BuildContext")
    @patch("samcli.lib.build.app_builder.ApplicationBuilder")
    def test_must_catch_known_exceptions(self, exception, wrapped_exception, ApplicationBuilderMock, BuildContextMock):

        ctx_mock = Mock()
        BuildContextMock.return_value.__enter__ = Mock()
        BuildContextMock.return_value.__enter__.return_value = ctx_mock
        builder_mock = ApplicationBuilderMock.return_value = Mock()

        builder_mock.build.side_effect = exception

        with self.assertRaises(UserException) as ctx:
            do_cli(
                "function_identifier",
                "template",
                "base_dir",
                "build_dir",
                "cache_dir",
                "clean",
                "use_container",
                "cached",
                "parallel",
                "manifest_path",
                "docker_network",
                "skip_pull",
                "parameteroverrides",
                "mode",
                (""),
                "container_env_var_file",
                (),
                "CFN",
                Mock(),
                Mock(),
            )

        self.assertEqual(str(ctx.exception), str(exception))
        self.assertEqual(wrapped_exception, ctx.exception.wrapped_from)

    @patch("samcli.commands.build.build_context.BuildContext")
    @patch("samcli.lib.build.app_builder.ApplicationBuilder")
    def test_must_catch_function_not_found_exception(self, ApplicationBuilderMock, BuildContextMock):
        ctx_mock = Mock()
        BuildContextMock.return_value.__enter__ = Mock()
        BuildContextMock.return_value.__enter__.return_value = ctx_mock
        ApplicationBuilderMock.side_effect = FunctionNotFound("Function Not Found")
        iac = Mock()
        project = Mock()

        with self.assertRaises(UserException) as ctx:
            do_cli(
                "function_identifier",
                "template",
                "base_dir",
                "build_dir",
                "cache_dir",
                "clean",
                "use_container",
                "cached",
                "parallel",
                "manifest_path",
                "docker_network",
                "skip_pull",
                "parameteroverrides",
                "mode",
                (""),
                "container_env_var_file",
                (),
                "CFN",
                iac,
                project,
            )

        self.assertEqual(str(ctx.exception), "Function Not Found")


class TestGetModeValueFromEnvvar(TestCase):
    def setUp(self):
        self.original = os.environ.copy()
        self.varname = "SOME_ENVVAR"
        self.choices = ["A", "B", "C"]

    def tearDown(self):
        os.environ = self.original

    def test_must_get_value(self):

        os.environ[self.varname] = "A"
        result = _get_mode_value_from_envvar(self.varname, self.choices)

        self.assertEqual(result, "A")

    def test_must_raise_if_value_not_in_choice(self):

        os.environ[self.varname] = "Z"

        with self.assertRaises(click.UsageError):
            _get_mode_value_from_envvar(self.varname, self.choices)

    def test_return_none_if_value_not_found(self):

        result = _get_mode_value_from_envvar(self.varname, self.choices)
        self.assertIsNone(result)


class TestEnvVarParsing(TestCase):
    def test_process_global_env_var(self):
        container_env_vars = ["ENV_VAR1=1", "ENV_VAR2=2"]

        result = _process_env_var(container_env_vars)
        self.assertEqual(result, {"Parameters": {"ENV_VAR1": "1", "ENV_VAR2": "2"}})

    def test_process_function_env_var(self):
        container_env_vars = ["Function1.ENV_VAR1=1", "Function2.ENV_VAR2=2"]

        result = _process_env_var(container_env_vars)
        self.assertEqual(result, {"Function1": {"ENV_VAR1": "1"}, "Function2": {"ENV_VAR2": "2"}})

    def test_irregular_env_var_value(self):
        container_env_vars = ["TEST_VERSION=1.2.3"]

        result = _process_env_var(container_env_vars)
        self.assertEqual(result, {"Parameters": {"TEST_VERSION": "1.2.3"}})

    def test_invalid_function_env_var(self):
        container_env_vars = ["Function1.ENV_VAR1=", "Function2.ENV_VAR2=2"]

        result = _process_env_var(container_env_vars)
        self.assertEqual(result, {"Function2": {"ENV_VAR2": "2"}})

    def test_invalid_global_env_var(self):
        container_env_vars = ["ENV_VAR1", "Function2.ENV_VAR2=2"]

        result = _process_env_var(container_env_vars)
        self.assertEqual(result, {"Function2": {"ENV_VAR2": "2"}})

    def test_none_env_var_does_not_error_out(self):
        container_env_vars = None

        result = _process_env_var(container_env_vars)
        self.assertEqual(result, {})


class TestImageParsing(TestCase):
    def check(self, image_options, expected):
        self.assertEqual(_process_image_options(image_options), expected)

    def test_empty_list(self):
        self.check([], {})

    def test_default_image(self):
        self.check(["image1"], {None: "image1"})

    def test_one_function_image(self):
        self.check(["Function1=image1"], {"Function1": "image1"})

    def test_one_function_with_default_image(self):
        self.check(["Function1=image1", "image2"], {"Function1": "image1", None: "image2"})

    def test_two_functions_with_default_image(self):
        self.check(
            ["Function1=image1", "Function2=image2", "image3"],
            {"Function1": "image1", "Function2": "image2", None: "image3"},
        )
