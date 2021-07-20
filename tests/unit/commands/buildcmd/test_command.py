import os
import click

from unittest import TestCase
from unittest.mock import Mock, patch
from parameterized import parameterized

from samcli.commands.build.command import do_cli, _get_mode_value_from_envvar, _process_env_var, _process_image_options


class TestDoCli(TestCase):
    @patch("samcli.commands.build.command.click")
    @patch("samcli.commands.build.build_context.BuildContext")
    @patch("samcli.commands.build.command.os")
    def test_must_succeed_build(self, os_mock, BuildContextMock, mock_build_click):

        ctx_mock = Mock()
        BuildContextMock.return_value.__enter__.return_value = ctx_mock

        do_cli(
            ctx_mock,
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
            "skip_pull_image",
            "parameter_overrides",
            "mode",
            (""),
            "container_env_var_file",
            (),
        )

        BuildContextMock.assert_called_with(
            "function_identifier",
            "template",
            "base_dir",
            "build_dir",
            "cache_dir",
            "cached",
            clean="clean",
            use_container="use_container",
            parallel="parallel",
            parameter_overrides="parameter_overrides",
            manifest_path="manifest_path",
            docker_network="docker_network",
            skip_pull_image="skip_pull_image",
            mode="mode",
            container_env_var={},
            container_env_var_file="container_env_var_file",
            build_images={},
            aws_region=ctx_mock.region,
        )
        ctx_mock.run.assert_called_with()
        self.assertEqual(ctx_mock.run.call_count, 1)


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
