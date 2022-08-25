import os
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
from parameterized import parameterized

from samcli.commands.exceptions import InvalidEnvironmentVariableException, ReservedEnvironmentVariableException
from samcli.commands.test_runner.run.cli import _get_unique_bucket_directory_name, _validate_other_env_vars, do_cli
from samcli.lib.test_runner.fargate_testsuite_runner import FargateTestsuiteRunner


class TestEnvVarValidation(TestCase):
    def test_invalid_var_names(self):
        other_env_vars = {r"0variable_name": "value", r"\othervariable_name": "othervalue"}
        with self.assertRaises(InvalidEnvironmentVariableException):
            _validate_other_env_vars(other_env_vars, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)

    def test_none_value(self):
        other_env_vars = {"key": None}
        with self.assertRaises(InvalidEnvironmentVariableException):
            _validate_other_env_vars(other_env_vars, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)

    def test_object_value(self):
        other_env_vars = {"key": {"otherkey": "otherval"}}
        with self.assertRaises(InvalidEnvironmentVariableException):
            _validate_other_env_vars(other_env_vars, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)

    def test_list_value(self):
        other_env_vars = {"key": [1, 2, 3]}
        with self.assertRaises(InvalidEnvironmentVariableException):
            _validate_other_env_vars(other_env_vars, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)

    @parameterized.expand(list(FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES))
    def test_reserved_name_specified(self, reserved_name):
        other_env_vars = {reserved_name: "oh-no"}
        with self.assertRaises(ReservedEnvironmentVariableException):
            _validate_other_env_vars(other_env_vars, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)

    def test_empty_env_vars(self):
        _validate_other_env_vars({}, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)

    def test_valid_env_vars(self):
        other_env_vars = {"key1": 5, "key2": 3.14, "key3": "this is a string"}
        _validate_other_env_vars(other_env_vars, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)


class TestDefaultDirectoryName(TestCase):
    @patch("samcli.commands.test_runner.run.cli.datetime")
    def test_get_unique_bucket_directory_name(self, datetime_patch) -> str:
        # Example date
        # Patching datetime.now().isoformat()
        datetime_patch.now.return_value.isoformat.return_value = "2022-08-11T11:13:07.793055"

        result = _get_unique_bucket_directory_name()

        self.assertEqual(result, "test_run_2022_08_11T11_13_07")


class TestCli(TestCase):
    def setUp(self):
        mock_context = Mock()
        mock_context.profile = "test-profile"
        mock_context.region = "test-region"
        self.do_cli_params = {
            "ctx": mock_context,
            "runner_stack_name": "test-stack-name",
            "runner_template_path": "fake/path/template.yaml",
            "env_file": "fake/path/env_vars.yaml",
            "test_command_options": "--option",
            "tests_path": "fake/path/tests",
            "requirements_file_path": "fake/path/requirements.txt",
            "bucket_override": None,
            "path_in_bucket": "fake/path/in/bucket",
            "ecs_cluster_override": None,
            "subnets_override": None,
        }

    def test_bad_yaml_file(self):
        temp_yaml_name = "test-yaml-file.yaml"
        with open(temp_yaml_name, "w") as f:
            f.write("KEYnovalue")

        self.do_cli_params["env_file"] = temp_yaml_name
        try:
            with self.assertRaises(InvalidEnvironmentVariableException):
                do_cli(**self.do_cli_params)
        finally:
            os.remove(temp_yaml_name)

    @patch("samcli.lib.test_runner.fargate_testsuite_runner.FargateTestsuiteRunner")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    def test_good_run(self, get_boto_client_provider_patch, FargateTestsuiteRunnerPatch):
        temp_yaml_name = "test-good-yaml.yaml"
        with open(temp_yaml_name, "w") as f:
            f.write("KEY1: VALUE1")

        try:
            self.do_cli_params["env_file"] = temp_yaml_name
            boto_client_provider_mock = Mock()
            get_boto_client_provider_patch.return_value = boto_client_provider_mock
            runnerMock = Mock()
            runnerMock.do_testsuite = Mock()
            # Exit code
            runnerMock.do_testsuite.return_value = 0
            FargateTestsuiteRunnerPatch.return_value = runnerMock

            with pytest.raises(SystemExit) as pytest_wrapped_exit:
                do_cli(**self.do_cli_params)
                self.assertEqual(pytest_wrapped_exit.value.code, 0)

            get_boto_client_provider_patch.assert_called_with(region="test-region", profile="test-profile")
            FargateTestsuiteRunnerPatch.assert_called_with(
                boto_client_provider=boto_client_provider_mock,
                runner_stack_name=self.do_cli_params["runner_stack_name"],
                tests_path=self.do_cli_params["tests_path"],
                requirements_file_path=self.do_cli_params["requirements_file_path"],
                path_in_bucket=self.do_cli_params["path_in_bucket"],
                other_env_vars={"KEY1": "VALUE1"},
                bucket_override=self.do_cli_params["bucket_override"],
                ecs_cluster_override=self.do_cli_params["ecs_cluster_override"],
                subnets_override=self.do_cli_params["subnets_override"],
                test_command_options=self.do_cli_params["test_command_options"],
                runner_template_path=self.do_cli_params["runner_template_path"],
            )
            runnerMock.do_testsuite.assert_called_once()
        finally:
            os.remove(temp_yaml_name)
