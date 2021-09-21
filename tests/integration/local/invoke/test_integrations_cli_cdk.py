import json
from distutils.dir_util import copy_tree

from subprocess import Popen, PIPE, TimeoutExpired
from timeit import default_timer as timer
import pytest

from .invoke_integ_base import CDKInvokeIntegPythonBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY, run_command

# Layers tests require credentials and Appveyor will only add credentials to the env if the PR is from the same repo.
# This is to restrict layers tests to run outside of Appveyor,
# when the branch is not master and tests are not run by Canary.
SKIP_LAYERS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


TIMEOUT = 300


class TestCdkPythonHelloWorldIntegration(CDKInvokeIntegPythonBase):
    def setUp(self):
        super().setUp()
        self.construct_definition_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(self.construct_definition_path, self.working_dir)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returncode_is_zero(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/helloworld-serverless-function", event_path=self.event_path
        )
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(process_execute.process.returncode, 0)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_utf8_event(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/helloworld-serverless-function", event_path=self.event_utf8_path
        )
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(process_execute.process.returncode, 0)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_results(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/helloworld-serverless-function", event_path=self.event_path
        )

        process_execute = run_command(command_list, cwd=self.working_dir)

        process_stdout = process_execute.stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_timeout_set(self):
        command_list = self.get_command_list("AwsLambdaFunctionStack/timeout-function", event_path=self.event_path)

        start = timer()

        process_execute = run_command(command_list, cwd=self.working_dir)

        end = timer()

        wall_clock_cli_duration = end - start

        process_stdout = process_execute.stdout.strip()

        # validate the time of the cli (timeout is set to 5s)
        self.assertGreater(wall_clock_cli_duration, 5)
        self.assertLess(wall_clock_cli_duration, 20)

        self.assertEqual(process_execute.process.returncode, 0)
        self.assertEqual(
            process_stdout.decode("utf-8"),
            '""',
            msg="The return statement in the LambdaFunction " "should never return leading to an empty string",
        )

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_vars(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/custom-env-vars-function", event_path=self.event_path
        )

        process_execute = run_command(command_list, cwd=self.working_dir)
        process_stdout = process_execute.stdout.strip()

        self.assertEqual(process_stdout.decode("utf-8"), '"MyVar"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_when_function_writes_stdout(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/write-to-stdout-function", event_path=self.event_path
        )

        process_execute = run_command(command_list, cwd=self.working_dir)

        process_stdout = process_execute.stdout.strip()
        process_stderr = process_execute.stderr.strip()

        self.assertIn("Docker Lambda is writing to stdout", process_stderr.decode("utf-8"))
        self.assertIn("wrote to stdout", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_when_function_writes_stderr(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/write-to-stderr-function", event_path=self.event_path
        )

        process_execute = run_command(command_list, cwd=self.working_dir)

        process_stderr = process_execute.stderr.strip()

        self.assertIn("Docker Lambda is writing to stderr", process_stderr.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_result_when_no_event_given(self):
        command_list = self.get_command_list("AwsLambdaFunctionStack/echo-event-function")

        process_execute = run_command(command_list, cwd=self.working_dir)

        process_stdout = process_execute.stdout.strip()

        self.assertEqual(process_execute.process.returncode, 0)
        self.assertEqual("{}", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_parameters_overrides(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/echo-env-with-parameters",
            event_path=self.event_path,
            parameter_overrides={"MyRuntimeVersion": "v0", "TimeOut": "100"},
        )

        process_execute = run_command(command_list, cwd=self.working_dir)
        process_stdout = process_execute.stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertIsNone(environ.get("TimeOut"))
        self.assertEqual(environ["MyRuntimeVersion"], "v0")
        self.assertEqual(environ["EmptyDefaultParameter"], "")

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_results_python_function_construct(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/python-function-construct", event_path=self.event_path
        )

        process_execute = run_command(command_list, cwd=self.working_dir)
        process_stdout = process_execute.stdout.strip()

        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_results_docker_lambda_construct(self):
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/lambda-docker-function", event_path=self.event_path
        )

        process_execute = run_command(command_list, cwd=self.working_dir)
        process_stdout = process_execute.stdout.strip()
        out = json.loads(process_stdout)

        self.assertEqual(json.loads(out.get("body")).get("message"), "Hello world from Docker!")
