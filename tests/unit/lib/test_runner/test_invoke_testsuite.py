from botocore.exceptions import ClientError, WaiterError
from unittest import TestCase
from unittest.mock import Mock
from samcli.lib.test_runner.invoke_testsuite import invoke_testsuite
from samcli.commands.exceptions import ReservedEnvironmentVariableException


class Test_InvokeTestsuite(TestCase):
    def setUp(self):
        self.params = {
            "boto_ecs_client": None,
            "boto_s3_client": None,
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

        with self.assertRaises(ValueError):
            invoke_testsuite(**self.params)

    def test_specify_variable_bucket(self):
        self.params["other_env_vars"] = {"TEST_RUNNER_BUCKET": "oh-no"}
        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**self.params)

    def test_specify_variable_run_id(self):
        self.params["other_env_vars"] = {"TEST_RUN_ID": "oh-no"}
        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**self.params)

    def test_specify_variable_command_options(self):
        self.params["other_env_vars"] = {"TEST_COMMAND_OPTIONS": "oh-no"}
        with self.assertRaises(ReservedEnvironmentVariableException):
            invoke_testsuite(**self.params)

    def test_bad_runtask(self):
        boto_ecs_client_mock = Mock()

        client_error_response = {"Error": {"Code": "Error Code", "Message": "Error Message"}}

        boto_ecs_client_mock.run_task.side_effect = ClientError(
            error_response=client_error_response, operation_name="run_task"
        )

        self.params["boto_ecs_client"] = boto_ecs_client_mock

        with self.assertRaises(ClientError):
            invoke_testsuite(**self.params)

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

        self.params["boto_ecs_client"] = boto_ecs_client_mock
        self.params["boto_s3_client"] = boto_s3_client_mock

        with self.assertRaises(WaiterError):
            invoke_testsuite(**self.params)
