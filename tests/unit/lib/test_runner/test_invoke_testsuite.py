from botocore.exceptions import ClientError
from unittest.mock import patch
from unittest import TestCase
from samcli.lib.test_runner.invoke_testsuite import invoke_testsuite, get_subnets
from samcli.commands.exceptions import ReservedEnvironmentVariableException
from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config


class Test_TemplateGenerator(TestCase):

    @patch("samcli.lib.test_runner.invoke_testsuite.get_subnets")
    def test_specify_reserved_variable(self, get_subnets_patch):
        """
        Ensure that customers cannot specify environment variables named BUCKET, TEST_RUN_ID, or OPTIONS
        """
        get_subnets_patch.return_value = ["subnet-xxxxxxxxxxxxxxxxx"]
        params = {
            "boto_client_provider": None,
            "bucket": "test-bucket-name",
            "path_in_bucket": "test_bucket_path",
            "ecs_cluster": "test-cluster-name",
            "container_name": "test-container-name",
            "task_definition_arn": "test-task-def-arn",
            "other_env_vars": {"BUCKET": "oh-no"},
            "test_command_options": "--max-fail=1",
            "do_await": False,
        }

        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**params)

        params["other_env_vars"] = {"TEST_RUN_ID": "oh-no"}

        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**params)

        params["other_env_vars"] = {"OPTIONS": "oh-no"}

        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**params)

    def test_get_subnets(self):
        boto_client_provider = get_boto_client_provider_with_config()

        subnets = get_subnets(boto_client_provider)

        self.assertGreaterEqual(len(subnets), 1)

        for subnet in subnets:
            self.assertRegex(subnet, r"subnet-[a-z0-9]{17}")

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
            "do_await": False,
        }

        with self.assertRaises(ClientError):
            invoke_testsuite(**params)


