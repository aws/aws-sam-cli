from botocore.exceptions import ClientError, WaiterError
from unittest import TestCase
from unittest.mock import Mock
from samcli.lib.test_runner.invoke_testsuite import FargateTestsuiteRunner
from samcli.commands.exceptions import InvalidEnvironmentVariableNameException, ReservedEnvironmentVariableException
from parameterized import parameterized


class Test_InvokeTestsuite(TestCase):
    def setUp(self):
        self.runner = FargateTestsuiteRunner(None, None)
        self.params = {
            "bucket": "test-bucket-name",
            "path_in_bucket": "test_bucket_path",
            "ecs_cluster": "test-cluster-name",
            "container_name": "test-container-name",
            "task_definition_arn": "test-task-def-arn",
            "other_env_vars": {},
            "test_command_options": "--max-fail=1",
            "subnets": ["subnet-xxxxxxxxxxxxxxxxx"],
        }

    def test_invalid_var_names(self):
        self.params["other_env_vars"] = {r"0variable_name": "value", r"\othervariable_name": "othervalue"}
        with self.assertRaises(InvalidEnvironmentVariableNameException):
            self.runner.invoke_testsuite(**self.params)

    @parameterized.expand(list(FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES))
    def test_reserved_name_specified(self, reserved_name: str):
        self.params["other_env_vars"] = {reserved_name: "oh-no"}
        with self.assertRaises(ReservedEnvironmentVariableException):
            self.runner.invoke_testsuite(**self.params)

    def test_bad_runtask(self):
        boto_ecs_client_mock = Mock()
        client_error_response = {"Error": {"Code": "Error Code", "Message": "Error Message"}}
        boto_ecs_client_mock.run_task.side_effect = ClientError(
            error_response=client_error_response, operation_name="run_task"
        )
        self.runner.boto_ecs_client = boto_ecs_client_mock
        with self.assertRaises(ClientError):
            self.runner.invoke_testsuite(**self.params)

    def test_results_waiter_fails(self):
        boto_ecs_client_mock = Mock()
        boto_ecs_client_mock.run_task.return_value = None
        boto_s3_client_mock = Mock()
        s3_waiter_mock = Mock()
        s3_waiter_mock.wait.side_effect = WaiterError(
            name="ObjectExists",
            reason="Max attempts suceeded, results failed to appear in the bucket.",
            last_response=None,
        )
        boto_s3_client_mock.get_waiter.return_value = s3_waiter_mock
        self.runner.boto_ecs_client = boto_ecs_client_mock
        self.runner.boto_s3_client = boto_s3_client_mock
        with self.assertRaises(WaiterError):
            self.runner.invoke_testsuite(**self.params)
