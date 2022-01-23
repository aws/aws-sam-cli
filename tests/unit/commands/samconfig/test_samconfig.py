"""
Tests whether SAM Config is being read by all CLI commands
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from contextlib import contextmanager
from samcli.commands._utils.experimental import ExperimentalFlag, set_experimental
from samcli.lib.config.samconfig import SamConfig, DEFAULT_ENV

from click.testing import CliRunner

from unittest import TestCase
from unittest.mock import patch, ANY
import logging

from samcli.lib.utils.packagetype import ZIP, IMAGE

LOG = logging.getLogger()
logging.basicConfig()


class TestSamConfigForAllCommands(TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()

        self.scratch_dir = tempfile.mkdtemp()
        Path(self.scratch_dir, "envvar.json").write_text("{}")
        Path(self.scratch_dir, "container-envvar.json").write_text("{}")

        os.chdir(self.scratch_dir)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.scratch_dir)
        self.scratch_dir = None

    @patch("samcli.commands.init.do_cli")
    def test_init(self, do_cli_mock):
        config_values = {
            "no_interactive": True,
            "location": "github.com",
            "runtime": "nodejs10.x",
            "dependency_manager": "maven",
            "output_dir": "myoutput",
            "name": "myname",
            "app_template": "apptemplate",
            "no_input": True,
            "extra_context": '{"key": "value", "key2": "value2"}',
        }

        with samconfig_parameters(["init"], self.scratch_dir, **config_values) as config_path:
            from samcli.commands.init import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                True,
                "github.com",
                False,
                ZIP,
                "nodejs10.x",
                None,
                None,
                "maven",
                "myoutput",
                "myname",
                "apptemplate",
                True,
                '{"key": "value", "key2": "value2"}',
            )

    @patch("samcli.commands.validate.validate.do_cli")
    def test_validate(self, do_cli_mock):
        config_values = {"template_file": "mytemplate.yaml"}

        with samconfig_parameters(["validate"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.validate.validate import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(ANY, str(Path(os.getcwd(), "mytemplate.yaml")))

    @patch("samcli.commands.build.command.do_cli")
    def test_build(self, do_cli_mock):
        config_values = {
            "resource_logical_id": "foo",
            "template_file": "mytemplate.yaml",
            "base_dir": "basedir",
            "build_dir": "builddir",
            "cache_dir": "cachedir",
            "cache": False,
            "use_container": True,
            "manifest": "requirements.txt",
            "docker_network": "mynetwork",
            "skip_pull_image": True,
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value ParameterKey=Key2,ParameterValue=Value2",
            "container_env_var": (""),
            "container_env_var_file": "file",
            "build_image": (""),
        }

        with samconfig_parameters(["build"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.build.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "foo",
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "basedir",
                "builddir",
                "cachedir",
                True,
                True,
                False,
                False,
                "requirements.txt",
                "mynetwork",
                True,
                {"Key": "Value", "Key2": "Value2"},
                None,
                (),
                "file",
                (),
            )

    @patch("samcli.commands.build.command.do_cli")
    def test_build_with_container_env_vars(self, do_cli_mock):
        config_values = {
            "resource_logical_id": "foo",
            "template_file": "mytemplate.yaml",
            "base_dir": "basedir",
            "build_dir": "builddir",
            "cache_dir": "cachedir",
            "cache": False,
            "use_container": True,
            "manifest": "requirements.txt",
            "docker_network": "mynetwork",
            "skip_pull_image": True,
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value ParameterKey=Key2,ParameterValue=Value2",
            "container_env_var": (""),
            "container_env_var_file": "env_vars_file",
        }

        with samconfig_parameters(["build"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.build.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "foo",
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "basedir",
                "builddir",
                "cachedir",
                True,
                True,
                False,
                False,
                "requirements.txt",
                "mynetwork",
                True,
                {"Key": "Value", "Key2": "Value2"},
                None,
                (),
                "env_vars_file",
                (),
            )

    @patch("samcli.commands.build.command.do_cli")
    def test_build_with_build_images(self, do_cli_mock):
        config_values = {
            "resource_logical_id": "foo",
            "template_file": "mytemplate.yaml",
            "base_dir": "basedir",
            "build_dir": "builddir",
            "cache_dir": "cachedir",
            "cache": False,
            "use_container": True,
            "manifest": "requirements.txt",
            "docker_network": "mynetwork",
            "skip_pull_image": True,
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value ParameterKey=Key2,ParameterValue=Value2",
            "build_image": ["Function1=image_1", "image_2"],
        }

        with samconfig_parameters(["build"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.build.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "foo",
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "basedir",
                "builddir",
                "cachedir",
                True,
                True,
                False,
                False,
                "requirements.txt",
                "mynetwork",
                True,
                {"Key": "Value", "Key2": "Value2"},
                None,
                (),
                None,
                ("Function1=image_1", "image_2"),
            )

    @patch("samcli.commands.local.invoke.cli.do_cli")
    def test_local_invoke(self, do_cli_mock):
        config_values = {
            "function_logical_id": "foo",
            "template_file": "mytemplate.yaml",
            "event": "event",
            "no_event": False,
            "env_vars": "envvar.json",
            "debug_port": [1, 2, 3],
            "debug_args": "args",
            "debugger_path": "mypath",
            "container_env_vars": "container-envvar.json",
            "docker_volume_basedir": "basedir",
            "docker_network": "mynetwork",
            "log_file": "logfile",
            "layer_cache_basedir": "basedir",
            "skip_pull_image": True,
            "force_image_build": True,
            "shutdown": True,
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value ParameterKey=Key2,ParameterValue=Value2",
            "invoke_image": ["image"],
        }

        # NOTE: Because we don't load the full Click BaseCommand here, this is mounted as top-level command
        with samconfig_parameters(["invoke"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.local.invoke.cli import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "foo",
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "event",
                False,
                "envvar.json",
                (1, 2, 3),
                "args",
                "mypath",
                "container-envvar.json",
                "basedir",
                "mynetwork",
                "logfile",
                "basedir",
                True,
                True,
                True,
                {"Key": "Value", "Key2": "Value2"},
                "localhost",
                "127.0.0.1",
                ("image",),
            )

    @patch("samcli.commands.local.start_api.cli.do_cli")
    def test_local_start_api(self, do_cli_mock):

        config_values = {
            "template_file": "mytemplate.yaml",
            "host": "127.0.0.1",
            "port": 12345,
            "static_dir": "static_dir",
            "env_vars": "envvar.json",
            "debug_port": [1, 2, 3],
            "debug_args": "args",
            "debugger_path": "mypath",
            "container_env_vars": "container-envvar.json",
            "docker_volume_basedir": "basedir",
            "docker_network": "mynetwork",
            "log_file": "logfile",
            "layer_cache_basedir": "basedir",
            "skip_pull_image": True,
            "force_image_build": True,
            "shutdown": False,
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value ParameterKey=Key2,ParameterValue=Value2",
            "invoke_image": ["image"],
        }

        # NOTE: Because we don't load the full Click BaseCommand here, this is mounted as top-level command
        with samconfig_parameters(["start-api"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.local.start_api.cli import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "127.0.0.1",
                12345,
                "static_dir",
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "envvar.json",
                (1, 2, 3),
                "args",
                "mypath",
                "container-envvar.json",
                "basedir",
                "mynetwork",
                "logfile",
                "basedir",
                True,
                True,
                {"Key": "Value", "Key2": "Value2"},
                None,
                False,
                None,
                "localhost",
                "127.0.0.1",
                ("image",),
            )

    @patch("samcli.commands.local.start_lambda.cli.do_cli")
    def test_local_start_lambda(self, do_cli_mock):

        config_values = {
            "template_file": "mytemplate.yaml",
            "host": "127.0.0.1",
            "port": 12345,
            "env_vars": "envvar.json",
            "debug_port": [1, 2, 3],
            "debug_args": "args",
            "debugger_path": "mypath",
            "container_env_vars": "container-envvar.json",
            "docker_volume_basedir": "basedir",
            "docker_network": "mynetwork",
            "log_file": "logfile",
            "layer_cache_basedir": "basedir",
            "skip_pull_image": True,
            "force_image_build": True,
            "shutdown": False,
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value",
            "invoke_image": ["image"],
        }

        # NOTE: Because we don't load the full Click BaseCommand here, this is mounted as top-level command
        with samconfig_parameters(["start-lambda"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.local.start_lambda.cli import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "127.0.0.1",
                12345,
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "envvar.json",
                (1, 2, 3),
                "args",
                "mypath",
                "container-envvar.json",
                "basedir",
                "mynetwork",
                "logfile",
                "basedir",
                True,
                True,
                {"Key": "Value"},
                None,
                False,
                None,
                "localhost",
                "127.0.0.1",
                ("image",),
            )

    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    @patch("samcli.commands.package.command.do_cli")
    def test_package(
        self,
        do_cli_mock,
        get_template_artifacts_format_mock,
        cli_validation_artifacts_format_mock,
        is_all_image_funcs_provided_mock,
    ):
        is_all_image_funcs_provided_mock.return_value = True
        cli_validation_artifacts_format_mock.return_value = [ZIP]
        get_template_artifacts_format_mock.return_value = [ZIP]
        config_values = {
            "template_file": "mytemplate.yaml",
            "s3_bucket": "mybucket",
            "force_upload": True,
            "s3_prefix": "myprefix",
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "kms_key_id": "mykms",
            "use_json": True,
            "metadata": '{"m1": "value1", "m2": "value2"}',
            "region": "myregion",
            "output_template_file": "output.yaml",
            "signing_profiles": "function=profile:owner",
        }

        with samconfig_parameters(["package"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.package.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "mybucket",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                None,
                "myprefix",
                "mykms",
                "output.yaml",
                True,
                True,
                False,
                {"m1": "value1", "m2": "value2"},
                {"function": {"profile_name": "profile", "profile_owner": "owner"}},
                "myregion",
                None,
                False,
            )

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    @patch("samcli.commands.package.command.do_cli")
    def test_package_with_image_repository_and_image_repositories(
        self, do_cli_mock, get_template_artifacts_format_mock
    ):

        get_template_artifacts_format_mock.return_value = [IMAGE]
        config_values = {
            "template_file": "mytemplate.yaml",
            "s3_bucket": "mybucket",
            "force_upload": True,
            "s3_prefix": "myprefix",
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "image_repositories": ["HelloWorldFunction=123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"],
            "kms_key_id": "mykms",
            "use_json": True,
            "metadata": '{"m1": "value1", "m2": "value2"}',
            "region": "myregion",
            "output_template_file": "output.yaml",
            "signing_profiles": "function=profile:owner",
        }

        with samconfig_parameters(["package"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.package.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            self.assertIsNotNone(result.exception)

    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    @patch("samcli.commands._utils.template.get_template_artifacts_format")
    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    @patch("samcli.commands.deploy.command.do_cli")
    def test_deploy(self, do_cli_mock, template_artifacts_mock1, template_artifacts_mock2, template_artifacts_mock3):

        template_artifacts_mock1.return_value = [ZIP]
        template_artifacts_mock2.return_value = [ZIP]
        template_artifacts_mock3.return_value = [ZIP]
        config_values = {
            "template_file": "mytemplate.yaml",
            "stack_name": "mystack",
            "s3_bucket": "mybucket",
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "force_upload": True,
            "s3_prefix": "myprefix",
            "kms_key_id": "mykms",
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value",
            "capabilities": "cap1 cap2",
            "no_execute_changeset": True,
            "role_arn": "arn",
            "notification_arns": "notify1 notify2",
            "fail_on_empty_changeset": True,
            "use_json": True,
            "tags": 'a=tag1 b="tag with spaces"',
            "metadata": '{"m1": "value1", "m2": "value2"}',
            "guided": True,
            "confirm_changeset": True,
            "region": "myregion",
            "signing_profiles": "function=profile:owner",
            "disable_rollback": True,
        }

        with samconfig_parameters(["deploy"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.deploy.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "mystack",
                "mybucket",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                None,
                True,
                False,
                "myprefix",
                "mykms",
                {"Key": "Value"},
                ["cap1", "cap2"],
                True,
                "arn",
                ["notify1", "notify2"],
                True,
                True,
                {"a": "tag1", "b": "tag with spaces"},
                {"m1": "value1", "m2": "value2"},
                True,
                True,
                "myregion",
                None,
                {"function": {"profile_name": "profile", "profile_owner": "owner"}},
                False,
                "samconfig.toml",
                "default",
                False,
                True,
            )

    @patch("samcli.commands.deploy.command.do_cli")
    def test_deploy_image_repositories_and_image_repository(self, do_cli_mock):

        config_values = {
            "template_file": "mytemplate.yaml",
            "stack_name": "mystack",
            "s3_bucket": "mybucket",
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "image_repositories": ["HelloWorldFunction=123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"],
            "force_upload": True,
            "s3_prefix": "myprefix",
            "kms_key_id": "mykms",
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value",
            "capabilities": "cap1 cap2",
            "no_execute_changeset": True,
            "role_arn": "arn",
            "notification_arns": "notify1 notify2",
            "fail_on_empty_changeset": True,
            "use_json": True,
            "tags": 'a=tag1 b="tag with spaces"',
            "metadata": '{"m1": "value1", "m2": "value2"}',
            "guided": True,
            "confirm_changeset": True,
            "region": "myregion",
            "signing_profiles": "function=profile:owner",
        }

        with samconfig_parameters(["deploy"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.deploy.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])
            self.assertIsNotNone(result.exception)

    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    @patch("samcli.commands._utils.template.get_template_artifacts_format")
    @patch("samcli.commands.deploy.command.do_cli")
    def test_deploy_different_parameter_override_format(
        self, do_cli_mock, template_artifacts_mock1, template_artifacts_mock2, template_artifacts_mock3
    ):

        template_artifacts_mock1.return_value = [ZIP]
        template_artifacts_mock2.return_value = [ZIP]
        template_artifacts_mock3.return_value = [ZIP]

        config_values = {
            "template_file": "mytemplate.yaml",
            "stack_name": "mystack",
            "s3_bucket": "mybucket",
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "force_upload": True,
            "s3_prefix": "myprefix",
            "kms_key_id": "mykms",
            "parameter_overrides": 'Key1=Value1 Key2="Multiple spaces in the value"',
            "capabilities": "cap1 cap2",
            "no_execute_changeset": True,
            "role_arn": "arn",
            "notification_arns": "notify1 notify2",
            "fail_on_empty_changeset": True,
            "use_json": True,
            "tags": 'a=tag1 b="tag with spaces"',
            "metadata": '{"m1": "value1", "m2": "value2"}',
            "guided": True,
            "confirm_changeset": True,
            "region": "myregion",
            "signing_profiles": "function=profile:owner",
            "disable_rollback": True,
        }

        with samconfig_parameters(["deploy"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.deploy.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "mystack",
                "mybucket",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                None,
                True,
                False,
                "myprefix",
                "mykms",
                {"Key1": "Value1", "Key2": "Multiple spaces in the value"},
                ["cap1", "cap2"],
                True,
                "arn",
                ["notify1", "notify2"],
                True,
                True,
                {"a": "tag1", "b": "tag with spaces"},
                {"m1": "value1", "m2": "value2"},
                True,
                True,
                "myregion",
                None,
                {"function": {"profile_name": "profile", "profile_owner": "owner"}},
                False,
                "samconfig.toml",
                "default",
                False,
                True,
            )

    @patch("samcli.commands._utils.experimental.is_experimental_enabled")
    @patch("samcli.commands.logs.command.do_cli")
    def test_logs(self, do_cli_mock, experimental_mock):
        config_values = {
            "name": ["myfunction"],
            "stack_name": "mystack",
            "filter": "myfilter",
            "tail": True,
            "include_traces": False,
            "start_time": "starttime",
            "end_time": "endtime",
            "region": "myregion",
        }
        experimental_mock.return_value = False

        with samconfig_parameters(["logs"], self.scratch_dir, **config_values) as config_path:
            from samcli.commands.logs.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ("myfunction",),
                "mystack",
                "myfilter",
                True,
                False,
                "starttime",
                "endtime",
                (),
                False,
                "myregion",
                None,
            )

    @patch("samcli.commands._utils.experimental.is_experimental_enabled")
    @patch("samcli.commands.logs.command.do_cli")
    def test_logs_tail(self, do_cli_mock, experimental_mock):
        config_values = {
            "name": ["myfunction"],
            "stack_name": "mystack",
            "filter": "myfilter",
            "tail": True,
            "include_traces": True,
            "start_time": "starttime",
            "end_time": "endtime",
            "cw_log_group": ["cw_log_group"],
            "region": "myregion",
        }
        experimental_mock.return_value = True
        with samconfig_parameters(["logs"], self.scratch_dir, **config_values) as config_path:
            from samcli.commands.logs.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ("myfunction",),
                "mystack",
                "myfilter",
                True,
                True,
                "starttime",
                "endtime",
                ("cw_log_group",),
                False,
                "myregion",
                None,
            )

    @patch("samcli.commands.publish.command.do_cli")
    def test_publish(self, do_cli_mock):
        config_values = {"template_file": "mytemplate.yaml", "semantic_version": "0.1.1"}

        with samconfig_parameters(["publish"], self.scratch_dir, **config_values) as config_path:
            from samcli.commands.publish.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(ANY, str(Path(os.getcwd(), "mytemplate.yaml")), "0.1.1")

    def test_info_must_not_read_from_config(self):
        config_values = {"a": "b"}

        with samconfig_parameters([], self.scratch_dir, **config_values) as config_path:
            from samcli.cli.main import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, ["--info"])

            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            info_result = json.loads(result.output)
            self.assertTrue("version" in info_result)

    @patch("samcli.commands._utils.experimental.is_experimental_enabled")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    @patch("samcli.commands._utils.template.get_template_artifacts_format")
    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    @patch("samcli.commands.sync.command.do_cli")
    def test_sync(
        self,
        do_cli_mock,
        template_artifacts_mock1,
        template_artifacts_mock2,
        template_artifacts_mock3,
        is_all_image_funcs_provided_mock,
        experimental_mock,
    ):

        template_artifacts_mock1.return_value = [ZIP]
        template_artifacts_mock2.return_value = [ZIP]
        template_artifacts_mock3.return_value = [ZIP]
        is_all_image_funcs_provided_mock.return_value = True
        experimental_mock.return_value = True

        config_values = {
            "template_file": "mytemplate.yaml",
            "stack_name": "mystack",
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "base_dir": "path",
            "s3_prefix": "myprefix",
            "kms_key_id": "mykms",
            "parameter_overrides": 'Key1=Value1 Key2="Multiple spaces in the value"',
            "capabilities": "cap1 cap2",
            "no_execute_changeset": True,
            "role_arn": "arn",
            "notification_arns": "notify1 notify2",
            "tags": 'a=tag1 b="tag with spaces"',
            "metadata": '{"m1": "value1", "m2": "value2"}',
            "guided": True,
            "confirm_changeset": True,
            "region": "myregion",
            "signing_profiles": "function=profile:owner",
        }

        with samconfig_parameters(["sync"], self.scratch_dir, **config_values) as config_path:
            from samcli.commands.sync.command import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                str(Path(os.getcwd(), "mytemplate.yaml")),
                False,
                False,
                (),
                (),
                True,
                "mystack",
                "myregion",
                None,
                "path",
                {"Key1": "Value1", "Key2": "Multiple spaces in the value"},
                None,
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                None,
                "myprefix",
                "mykms",
                ["cap1", "cap2"],
                "arn",
                ["notify1", "notify2"],
                {"a": "tag1", "b": "tag with spaces"},
                {"m1": "value1", "m2": "value2"},
                "samconfig.toml",
                "default",
            )


class TestSamConfigWithOverrides(TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()

        self.scratch_dir = tempfile.mkdtemp()
        Path(self.scratch_dir, "otherenvvar.json").write_text("{}")
        Path(self.scratch_dir, "other-containerenvvar.json").write_text("{}")

        os.chdir(self.scratch_dir)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.scratch_dir)
        self.scratch_dir = None

    @patch("samcli.commands.local.start_lambda.cli.do_cli")
    def test_override_with_cli_params(self, do_cli_mock):

        config_values = {
            "template_file": "mytemplate.yaml",
            "host": "127.0.0.1",
            "port": 12345,
            "env_vars": "envvar.json",
            "debug_port": [1, 2, 3],
            "debug_args": "args",
            "debugger_path": "mypath",
            "container_env_vars": "container-envvar.json",
            "docker_volume_basedir": "basedir",
            "docker_network": "mynetwork",
            "log_file": "logfile",
            "layer_cache_basedir": "basedir",
            "skip_pull_image": True,
            "force_image_build": True,
            "shutdown": False,
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value",
            "invoke_image": ["image"],
        }

        # NOTE: Because we don't load the full Click BaseCommand here, this is mounted as top-level command
        with samconfig_parameters(["start-lambda"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.local.start_lambda.cli import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "--template-file",
                    "othertemplate.yaml",
                    "--host",
                    "otherhost",
                    "--port",
                    9999,
                    "--env-vars",
                    "otherenvvar.json",
                    "--debug-port",
                    9,
                    "--debug-port",
                    8,
                    "--debug-port",
                    7,
                    "--debug-args",
                    "otherargs",
                    "--debugger-path",
                    "otherpath",
                    "--container-env-vars",
                    "other-containerenvvar.json",
                    "--docker-volume-basedir",
                    "otherbasedir",
                    "--docker-network",
                    "othernetwork",
                    "--log-file",
                    "otherlogfile",
                    "--layer-cache-basedir",
                    "otherbasedir",
                    "--skip-pull-image",
                    "--force-image-build",
                    "--shutdown",
                    "--parameter-overrides",
                    "A=123 C=D E=F12! G=H",
                    "--container-host",
                    "localhost",
                    "--container-host-interface",
                    "127.0.0.1",
                ],
            )

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "otherhost",
                9999,
                str(Path(os.getcwd(), "othertemplate.yaml")),
                "otherenvvar.json",
                (9, 8, 7),
                "otherargs",
                "otherpath",
                "other-containerenvvar.json",
                "otherbasedir",
                "othernetwork",
                "otherlogfile",
                "otherbasedir",
                True,
                True,
                {"A": "123", "C": "D", "E": "F12!", "G": "H"},
                None,
                True,
                None,
                "localhost",
                "127.0.0.1",
                ("image",),
            )

    @patch("samcli.commands.local.start_lambda.cli.do_cli")
    def test_override_with_cli_params_and_envvars(self, do_cli_mock):

        config_values = {
            "template_file": "mytemplate.yaml",
            "host": "127.0.0.1",
            "port": 12345,
            "env_vars": "envvar.json",
            "debug_port": [1, 2, 3],
            "debug_args": "args",
            "debugger_path": "mypath",
            "container_env_vars": "container-envvar.json",
            "docker_volume_basedir": "basedir",
            "docker_network": "mynetwork",
            "log_file": "logfile",
            "layer_cache_basedir": "basedir",
            "skip_pull_image": True,
            "force_image_build": False,
            "shutdown": False,
            "invoke_image": ["image"],
        }

        # NOTE: Because we don't load the full Click BaseCommand here, this is mounted as top-level command
        with samconfig_parameters(["start-lambda"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.local.start_lambda.cli import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(
                cli,
                env={
                    "SAM_TEMPLATE_FILE": "envtemplate.yaml",
                    "SAM_SKIP_PULL_IMAGE": "False",
                    "SAM_FORCE_IMAGE_BUILD": "False",
                    "SAM_DOCKER_NETWORK": "envnetwork",
                    # Debug port is exclusively provided through envvars and not thru CLI args
                    "SAM_DEBUG_PORT": "13579",
                    "DEBUGGER_ARGS": "envargs",
                    "SAM_DOCKER_VOLUME_BASEDIR": "envbasedir",
                    "SAM_LAYER_CACHE_BASEDIR": "envlayercache",
                },
                args=[
                    "--host",
                    "otherhost",
                    "--port",
                    9999,
                    "--env-vars",
                    "otherenvvar.json",
                    "--debugger-path",
                    "otherpath",
                    "--container-env-vars",
                    "other-containerenvvar.json",
                    "--log-file",
                    "otherlogfile",
                    # this is a case where cli args takes precedence over both
                    # config file and envvar
                    "--force-image-build",
                    # Parameter overrides is exclusively provided through CLI args and not config
                    "--parameter-overrides",
                    "A=123 C=D E=F12! G=H",
                ],
            )

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                ANY,
                "otherhost",
                9999,
                str(Path(os.getcwd(), "envtemplate.yaml")),
                "otherenvvar.json",
                (13579,),
                "envargs",
                "otherpath",
                "other-containerenvvar.json",
                "envbasedir",
                "envnetwork",
                "otherlogfile",
                "envlayercache",
                False,
                True,
                {"A": "123", "C": "D", "E": "F12!", "G": "H"},
                None,
                False,
                None,
                "localhost",
                "127.0.0.1",
                ("image",),
            )

    @patch("samcli.commands.validate.validate.do_cli")
    def test_secondary_option_name_template_validate(self, do_cli_mock):
        # "--template" is an alias of "--template-file"
        config_values = {"template": "mytemplate.yaml"}

        with samconfig_parameters(["validate"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.validate.validate import cli

            LOG.debug(Path(config_path).read_text())
            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(ANY, str(Path(os.getcwd(), "mytemplate.yaml")))


@contextmanager
def samconfig_parameters(cmd_names, config_dir=None, env=None, **kwargs):
    """
    ContextManager to write a new SAM Config and remove the file after the contextmanager exists

    Parameters
    ----------
    cmd_names : list(str)
        Name of the full commnad split as a list: ["generate-event", "s3", "put"]

    config_dir : str
        Path where the SAM config file should be written to. Defaults to os.getcwd()

    env : str
        Optional name of the config environment. This is currently unused

    kwargs : dict
        Parameter names and values to be written to the file.

    Returns
    -------
    Path to the config file
    """

    env = env or DEFAULT_ENV
    section = "parameters"
    samconfig = SamConfig(config_dir=config_dir)

    try:
        for k, v in kwargs.items():
            samconfig.put(cmd_names, section, k, v, env=env)

        samconfig.flush()
        yield samconfig.path()
    finally:
        Path(samconfig.path()).unlink()
