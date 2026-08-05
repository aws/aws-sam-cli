import json
import os
import click

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.build.command import do_cli, _get_mode_value_from_envvar
from samcli.commands.build.exceptions import MissingBuildMethodException
from samcli.commands.build.utils import MountMode
from samcli.commands.exceptions import UserException


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
            (),
            hook_name=None,
            build_in_source=False,
            mount_with=MountMode.READ,
            mount_symlinks=True,
            use_buildkit=False,
            language_extensions=None,
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
            excluded_resources=(),
            aws_region=ctx_mock.region,
            hook_name=None,
            build_in_source=False,
            mount_with=MountMode.READ,
            mount_symlinks=True,
            use_buildkit=False,
            language_extensions=None,
            output="text",
        )
        ctx_mock.run.assert_called_with()
        self.assertEqual(ctx_mock.run.call_count, 1)


class TestDoCliJsonFailure(TestCase):
    """do_cli centrally serializes failures to JSON in --output json mode, covering every
    UserException path (including non-BuildError ones the earlier per-exception handling missed)."""

    def _run_expecting(self, raised_exception):
        base_args = ["function_identifier", "template", "base_dir", "build_dir", "cache_dir", "clean"]
        echoed = []
        with patch("samcli.commands.build.build_context.BuildContext") as BuildContextMock:
            BuildContextMock.return_value.__enter__.return_value.run.side_effect = raised_exception
            with patch("samcli.commands.build.command.click.echo", side_effect=echoed.append):
                with self.assertRaises(type(raised_exception)):
                    do_cli(
                        Mock(),
                        *base_args,
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
                        (),
                        hook_name=None,
                        build_in_source=False,
                        mount_with=MountMode.READ,
                        mount_symlinks=True,
                        use_buildkit=False,
                        language_extensions=None,
                        output="json",
                    )
        return echoed

    def test_json_failure_includes_type_message_and_resource(self):
        # run() re-raises build failures as UserException, carrying wrapped_from + resource_name.
        ex = UserException("dependency failure", wrapped_from="WorkflowFailedError")
        ex.resource_name = "HelloWorldFunction"

        result = json.loads(self._run_expecting(ex)[0])

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["error"]["type"], "WorkflowFailedError")
        self.assertEqual(result["error"]["message"], "dependency failure")
        self.assertEqual(result["error"]["resource"], "HelloWorldFunction")

    def test_json_failure_for_non_build_error_user_exception(self):
        # MissingBuildMethodException is a UserException raised before/around run()'s try block.
        # Previously it exited 1 with empty stdout; do_cli's UserException handler must emit JSON.
        result = json.loads(self._run_expecting(MissingBuildMethodException("no build method"))[0])

        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["error"]["type"], "MissingBuildMethodException")


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
