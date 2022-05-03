import itertools
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple
from unittest import skipIf

import boto3
import pytest
import requests
from tests.integration.logs.logs_integ_base import RETRY_SLEEP
from parameterized import parameterized

from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.logs.logs_integ_base import LogsIntegBase, RETRY_COUNT
from tests.testing_utils import (
    run_command,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    start_persistent_process,
    read_until,
    kill_process,
    method_to_stack_name,
)

LOG = logging.getLogger(__name__)
SKIP_LOGS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_LOGS_TESTS, "Skip logs tests in CI/CD only")
class TestLogsCommand(LogsIntegBase):
    stack_name = ""
    stack_resources = []
    stack_info = None

    def setUp(self):
        self.lambda_client = boto3.client("lambda")
        self.sfn_client = boto3.client("stepfunctions")

    @pytest.fixture(autouse=True, scope="class")
    def sync_code_base(self):
        test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "logs")
        TestLogsCommand.stack_name = method_to_stack_name("sam_logs")
        LOG.info("Deploying stack %s", self.stack_name)
        deploy_cmd = DeployIntegBase.get_deploy_command_list(
            stack_name=self.stack_name,
            template_file=test_data_path.joinpath("python-apigw-sfn", "template.yaml"),
            resolve_s3=True,
            capabilities="CAPABILITY_IAM",
        )
        deploy_result = run_command(deploy_cmd)
        self.assertEqual(
            deploy_result.process.returncode, 0, f"Deployment of the test stack is failed with {deploy_result.stderr}"
        )

        cfn_client = boto3.client("cloudformation")
        cfn_resource = boto3.resource("cloudformation")
        TestLogsCommand.stack_resources = cfn_client.describe_stack_resources(StackName=TestLogsCommand.stack_name).get(
            "StackResources", []
        )
        TestLogsCommand.stack_info = cfn_resource.Stack(TestLogsCommand.stack_name)

        yield

        cfn_client.delete_stack(StackName=self.stack_name)

    def _get_physical_id(self, logical_id: str):
        for stack_resource in self.stack_resources:
            if stack_resource["LogicalResourceId"] == logical_id:
                return stack_resource["PhysicalResourceId"]

        return None

    def _get_output_value(self, key: str):
        for output in self.stack_info.outputs:
            if output.get("OutputKey", "") == key:
                return output.get("OutputValue", "")

        return None

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_function_logs(self, function_name: str):
        expected_log_output = f"Hello world from {function_name} function"
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name)
        self._check_logs(cmd_list, [expected_log_output])

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_tail(self, function_name: str):
        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name, tail=True)
        tail_process = start_persistent_process(cmd_list)

        expected_log_output = f"Hello world from {function_name} function"
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        def _check_logs(output: str, _: List[str]) -> bool:
            return expected_log_output in output

        try:
            read_until(tail_process, _check_logs, timeout=RETRY_COUNT * RETRY_SLEEP)
        finally:
            kill_process(tail_process)

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_filter(self, function_name: str):
        log_filter = "this should be filtered"
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name, filter=log_filter)
        self._check_logs(cmd_list, [log_filter])

    @parameterized.expand(itertools.product(["HelloWorldServerlessApi"], ["hello", "world"]))
    def test_apigw_logs(self, apigw_name: str, path: str):
        apigw_url = f"{self._get_output_value(apigw_name)}{path}"
        apigw_result = requests.get(apigw_url)
        LOG.info("APIGW result %s", apigw_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=apigw_name, beta_features=True)
        self._check_logs(cmd_list, [f"HTTP Method: GET, Resource Path: /{path}"])

    @parameterized.expand([("MyStateMachine",)])
    def test_sfn_logs(self, state_machine_name: str):
        sfn_physical_id = self._get_physical_id(state_machine_name)
        sfn_invoke_result = self.sfn_client.start_execution(stateMachineArn=sfn_physical_id)
        execution_arn = sfn_invoke_result.get("executionArn", "")
        LOG.info("SFN invoke result %s", sfn_invoke_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=state_machine_name, beta_features=True)
        self._check_logs(cmd_list, execution_arn)

    @parameterized.expand(itertools.product(["HelloWorldServerlessApi"], ["hello"]))
    def test_end_to_end_apigw(self, apigw_name: str, path: str):
        apigw_url = f"{self._get_output_value(apigw_name)}{path}"
        apigw_result = requests.get(apigw_url)
        LOG.info("APIGW result %s", apigw_result)
        cmd_list = self.get_logs_command_list(self.stack_name, beta_features=True)
        self._check_logs(
            cmd_list, [f"HTTP Method: GET, Resource Path: /{path}", "Hello world from ApiGwFunction function"]
        )

    @parameterized.expand(itertools.product(["HelloWorldServerlessApi"], ["world"]))
    def test_end_to_end_sfn(self, apigw_name: str, path: str):
        apigw_url = f"{self._get_output_value(apigw_name)}{path}"
        apigw_result = requests.get(apigw_url)
        LOG.info("APIGW result %s", apigw_result)
        cmd_list = self.get_logs_command_list(self.stack_name, beta_features=True)
        self._check_logs(
            cmd_list,
            [
                f"HTTP Method: GET, Resource Path: /{path}",
                '"type": "TaskStateEntered"',
                "Hello world from ApiGwFunction function",
            ],
        )

    @parameterized.expand(itertools.product(["ApiGwFunction", "SfnFunction"], [None, "text", "json"]))
    def test_output(self, function_name: str, output: Optional[str]):
        expected_log_output = f"Hello world from {function_name} function"
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name, output=output, beta_features=True)
        self._check_logs(cmd_list, [expected_log_output], output=output)

    @parameterized.expand(
        itertools.product(
            ["ApiGwFunction", "SfnFunction"],
            [
                (None, None, True),
                (None, "1 minute", True),
                ("1 minute", None, True),
                ("now", None, False),
            ],
        )
    )
    def test_start_end(self, function_name: str, start_end_time_params: Tuple[Optional[str], Optional[str], bool]):
        (start_time, end_time, should_succeed) = start_end_time_params
        expected_log_output = f"Hello world from {function_name} function"
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_logs_command_list(
            self.stack_name, name=function_name, start_time=start_time, end_time=end_time
        )

        if not should_succeed:
            with self.assertRaises(ValueError):
                self._check_logs(cmd_list, [expected_log_output], retries=2)
        else:
            self._check_logs(cmd_list, [expected_log_output])

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_include_traces(self, function_name: str):
        expected_log_output = f"Hello world from {function_name} function"
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_logs_command_list(
            self.stack_name, name=function_name, include_traces=True, beta_features=True
        )
        self._check_logs(cmd_list, ["New XRay Service Graph", "XRay Event at", expected_log_output])

    def _check_logs(self, cmd_list: List, log_strings: List[str], output: str = "text", retries=RETRY_COUNT):
        for _ in range(retries):
            cmd_result = run_command(cmd_list)
            cmd_stdout = cmd_result.stdout.decode("utf-8")
            self.assertEqual(cmd_result.process.returncode, 0)
            log_string_found = True
            for log_string in log_strings:
                if output == "json":
                    if f'"message": "{log_string}\\n"' not in cmd_stdout:
                        log_string_found = False
                        break
                else:
                    if log_string not in cmd_stdout:
                        log_string_found = False
                        break

            if log_string_found:
                return
            time.sleep(RETRY_SLEEP)

        raise ValueError(f"No match found for one of the expected log outputs '{log_strings}'")
