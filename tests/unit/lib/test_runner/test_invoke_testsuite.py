from botocore.exceptions import ClientError
from unittest import TestCase
from samcli.lib.test_runner.invoke_testsuite import invoke_testsuite
from samcli.commands.exceptions import ReservedEnvironmentVariableException
from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config


class Test_InvokeTestsuite(TestCase):
    def test_specify_reserved_variable(self):
        """
        Ensure that customers cannot specify environment variables named TEST_RUNNER_BUCKET, TEST_RUN_ID, or TEST_COMMAND_OPTIONS
        """

        params = {
            "boto_client_provider": None,
            "bucket": "test-bucket-name",
            "path_in_bucket": "test_bucket_path",
            "ecs_cluster": "test-cluster-name",
            "container_name": "test-container-name",
            "task_definition_arn": "test-task-def-arn",
            "other_env_vars": {"TEST_RUNNER_BUCKET": "oh-no"},
            "test_command_options": "--max-fail=1",
            "subnets": ["subnet-xxxxxxxxxxxxxxxxx"],
            "do_await": False,
        }

        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**params)

        params["other_env_vars"] = {"TEST_RUN_ID": "oh-no"}

        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**params)

        params["other_env_vars"] = {"TEST_COMMAND_OPTIONS": "oh-no"}

        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**params)


    def test_bad_params(self):
        boto_client_provider = get_boto_client_provider_with_config()
        params = {
            "boto_client_provider": boto_client_provider,
            "bucket": "test-bucket-name",
            "path_in_bucket": "test_bucket_path",
            "ecs_cluster": "this-ecs-cluster-does-not-exist",
            "container_name": "test-container-name",
            "task_definition_arn": "this-task-definition-does-not-exist",
            "other_env_vars": {},
            "test_command_options": "--max-fail=1",
            "subnets": ["subnet-xxxxxxxxxxxxxxxxx"],
            "do_await": False,
        }

        with self.assertRaises(ClientError):
            invoke_testsuite(**params)
