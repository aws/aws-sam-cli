import os
import click

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.build.command import do_cli, _get_mode_value_from_envvar


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
