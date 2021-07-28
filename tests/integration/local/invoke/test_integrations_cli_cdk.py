import json
import shutil
import os
import copy
import tempfile
from distutils.dir_util import copy_tree
from unittest import skipIf

from parameterized import parameterized, parameterized_class
from subprocess import Popen, PIPE, TimeoutExpired
from timeit import default_timer as timer
import pytest
import docker

from tests.integration.local.invoke.layer_utils import LayerUtils
from .invoke_integ_base import InvokeIntegBase, CDKInvokeIntegPythonBase
from tests.testing_utils import IS_WINDOWS, RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Layers tests require credentials and Appveyor will only add credentials to the env if the PR is from the same repo.
# This is to restrict layers tests to run outside of Appveyor, when the branch is not master and tests are not run by Canary.
SKIP_LAYERS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY

from pathlib import Path

TIMEOUT = 300


class TestCdkPythonHelloWorldIntegration(CDKInvokeIntegPythonBase):
    @pytest.mark.flaky(reruns=3)
    def test_invoke_returncode_is_zero(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/helloworld-serverless-function", event_path=self.event_path
        )
        process = Popen(command_list, stdout=PIPE, cwd=self.working_dir)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(process.returncode, 0)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_utf8_event(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/helloworld-serverless-function", event_path=self.event_utf8_path
        )

        process = Popen(command_list, stdout=PIPE, cwd=self.working_dir)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(process.returncode, 0)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_execpted_results(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/helloworld-serverless-function", event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE, cwd=self.working_dir)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_timeout_set(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list("AwsLambdaFunctionStack/timeout-function", event_path=self.event_path)

        start = timer()
        process = Popen(command_list, stdout=PIPE, cwd=self.working_dir)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        end = timer()

        wall_clock_cli_duration = end - start

        process_stdout = stdout.strip()

        # validate the time of the cli (timeout is set to 5s)
        self.assertGreater(wall_clock_cli_duration, 5)
        self.assertLess(wall_clock_cli_duration, 20)

        self.assertEqual(process.returncode, 0)
        self.assertEqual(
            process_stdout.decode("utf-8"),
            '""',
            msg="The return statement in the LambdaFunction " "should never return leading to an empty string",
        )

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_vars(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/custom-env-vars-function", event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE, cwd=self.working_dir)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"MyVar"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_when_function_writes_stdout(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/write-to-stdout-function", event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE, stderr=PIPE, cwd=self.working_dir)
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        process_stderr = stderr.strip()

        self.assertIn("Docker Lambda is writing to stdout", process_stderr.decode("utf-8"))
        self.assertIn("wrote to stdout", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_when_function_writes_stderr(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/write-to-stderr-function", event_path=self.event_path
        )

        process = Popen(command_list, stderr=PIPE, cwd=self.working_dir)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()

        self.assertIn("Docker Lambda is writing to stderr", process_stderr.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_result_when_no_event_given(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list("AwsLambdaFunctionStack/echo-event-function")
        process = Popen(command_list, stdout=PIPE, cwd=self.working_dir)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        self.assertEqual(process.returncode, 0)
        self.assertEqual("{}", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_parameters_overrides(self):
        test_data_path = self.test_data_path.joinpath("cdk", "python", "aws-lambda-function")
        copy_tree(test_data_path, self.working_dir)
        command_list = self.get_command_list(
            "AwsLambdaFunctionStack/echo-env-with-parameters",
            event_path=self.event_path,
            parameter_overrides={"MyRuntimeVersion": "v0", "TimeOut": "100"},
        )
        process = Popen(command_list, stdout=PIPE, cwd=self.working_dir)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))
        self.assertIsNone(environ.get("TimeOut"))
        self.assertEqual(environ["MyRuntimeVersion"], "v0")
        self.assertEqual(environ["EmptyDefaultParameter"], "")
