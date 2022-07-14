import itertools
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import boto3
import pytest
import requests
from parameterized import parameterized

from samcli.lib.utils.boto_utils import get_boto_resource_provider_with_config, get_boto_client_provider_with_config
from samcli.lib.utils.cloudformation import get_resource_summaries
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.logs.logs_integ_base import LogsIntegBase, RETRY_COUNT
from tests.integration.logs.logs_integ_base import RETRY_SLEEP
from tests.testing_utils import (
    start_persistent_process,
    read_until,
    kill_process,
    run_command,
    method_to_stack_name,
)

LOG = logging.getLogger(__name__)


class LogsIntegTestCases(LogsIntegBase):
    test_template_folder = ""

    stack_name = ""
    stack_resources = {}
    stack_info = None

    def setUp(self):
        self.lambda_client = boto3.client("lambda")
        self.sfn_client = boto3.client("stepfunctions")

    @pytest.fixture(scope="class")
    def deploy_testing_stack(self):
        test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "logs")
        LogsIntegTestCases.stack_name = method_to_stack_name("test_logs_command")
        cfn_client = boto3.client("cloudformation")
        deploy_cmd = DeployIntegBase.get_deploy_command_list(
            stack_name=LogsIntegTestCases.stack_name,
            template_file=test_data_path.joinpath(self.test_template_folder, "template.yaml"),
            resolve_s3=True,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
        )
        deploy_result = run_command(deploy_cmd)

        yield deploy_result, cfn_client

        cfn_client.delete_stack(StackName=LogsIntegTestCases.stack_name)

    @pytest.fixture(autouse=True, scope="class")
    def logs_base(self, deploy_testing_stack):
        deploy_result = deploy_testing_stack[0]
        self.assertEqual(
            deploy_result.process.returncode, 0, f"Deployment of the test stack is failed with {deploy_result.stderr}"
        )
        stack_resource_summaries = get_resource_summaries(
            get_boto_resource_provider_with_config(),
            get_boto_client_provider_with_config(),
            LogsIntegTestCases.stack_name,
        )
        LogsIntegTestCases.stack_resources = {
            resource_full_path: stack_resource_summary.physical_resource_id
            for resource_full_path, stack_resource_summary in stack_resource_summaries.items()
        }
        cfn_resource = boto3.resource("cloudformation")
        LogsIntegTestCases.stack_info = cfn_resource.Stack(LogsIntegTestCases.stack_name)

    def _get_physical_id(self, resource_path: str):
        return self.stack_resources[resource_path]

    def _get_output_value(self, key: str):
        for output in self.stack_info.outputs:
            if output.get("OutputKey", "") == key:
                return output.get("OutputValue", "")

        return None

    def _test_function_logs(self, function_name):
        expected_log_output = f"Hello world from {function_name} function"  # Hello world from ApiGwFunction function
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name)
        self._check_logs(cmd_list, [expected_log_output])

    def _test_tail(self, function_name):
        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name, tail=True)
        tail_process = start_persistent_process(cmd_list)
        expected_log_output = f"Hello world from {function_name} function"  # Hello world from ApiGwFunction function
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        def _check_logs(output: str, _: List[str]) -> bool:
            return expected_log_output in output

        try:
            read_until(tail_process, _check_logs, timeout=RETRY_COUNT * RETRY_SLEEP)
        finally:
            kill_process(tail_process)

    def _test_filter(self, function_name):
        function_name_for_filter = function_name.replace("/", "")
        log_filter = f"this should be filtered {function_name_for_filter}"  # this should be filtered ApiGwFunction
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name, filter=log_filter)
        self._check_logs(cmd_list, [log_filter])

    def _test_apigw_logs(self, apigw_name, path):
        # apigw name in output section doesn't have forward slashes
        apigw_name_from_output = apigw_name.replace("/", "")
        apigw_url = f"{self._get_output_value(apigw_name_from_output)}{path}"
        apigw_result = requests.get(apigw_url)
        LOG.info("APIGW result %s", apigw_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=apigw_name)
        self._check_logs(cmd_list, [f"HTTP Method: GET, Resource Path: /{path}"])

    def _test_sfn_logs(self, state_machine_name):
        sfn_physical_id = self._get_physical_id(state_machine_name)
        sfn_invoke_result = self.sfn_client.start_execution(stateMachineArn=sfn_physical_id)
        execution_arn = sfn_invoke_result.get("executionArn", "")
        LOG.info("SFN invoke result %s", sfn_invoke_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=state_machine_name)
        self._check_logs(cmd_list, [execution_arn])

    def _test_end_to_end_apigw(self, apigw_name, path):
        # apigw name in output section doesn't have forward slashes
        apigw_name_from_output = apigw_name.replace("/", "")
        apigw_url = f"{self._get_output_value(apigw_name_from_output)}{path}"
        apigw_result = requests.get(apigw_url)
        LOG.info("APIGW result %s", apigw_result)
        cmd_list = self.get_logs_command_list(self.stack_name)
        self._check_logs(
            cmd_list,
            [
                f"HTTP Method: GET, Resource Path: /{path}",
                # Hello world from HelloWorldServerlessApi/hello function
                f"Hello world from {apigw_name_from_output}/{path} function",
            ],
        )

    def _test_end_to_end_sfn(self, apigw_name, path):
        # apigw name in output section doesn't have forward slashes
        apigw_name_from_output = apigw_name.replace("/", "")
        apigw_url = f"{self._get_output_value(apigw_name_from_output)}{path}"
        apigw_result = requests.get(apigw_url)
        LOG.info("APIGW result %s", apigw_result)
        cmd_list = self.get_logs_command_list(self.stack_name)
        self._check_logs(
            cmd_list,
            [
                f"HTTP Method: GET, Resource Path: /{path}",
                '"type": "TaskStateEntered"',
                # Hello world from HelloWorldServerlessApi/world function
                f"Hello world from {apigw_name_from_output}/{path} function",
            ],
        )

    def _test_output(self, function_name, output):
        expected_log_output = f"Hello world from {function_name} function"  # Hello world from ApiGwFunction function
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name, output=output)
        self._check_logs(cmd_list, [expected_log_output], output=output)

    def _test_start_end(self, function_name, start_end_time_params):
        (start_time, end_time, should_succeed) = start_end_time_params
        expected_log_output = f"Hello world from {function_name} function"  # Hello world from ApiGwFunction function
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

    def _test_include_traces(self, function_name):
        expected_log_output = f"Hello world from {function_name} function"  # Hello world from ApiGwFunction function
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=self._get_physical_id(function_name))
        LOG.info("Lambda invoke result %s", lambda_invoke_result)
        cmd_list = self.get_logs_command_list(self.stack_name, name=function_name, include_traces=True)
        self._check_logs(cmd_list, ["New XRay Service Graph", "XRay Event [revision ", expected_log_output])

    def _check_logs(self, cmd_list: List, log_strings: List[str], output: str = "text", retries=RETRY_COUNT):
        for _ in range(retries):
            cmd_result = run_command(cmd_list)
            cmd_stdout = cmd_result.stdout.decode("utf-8")
            cmd_stderr = cmd_result.stderr.decode("utf-8")

            if cmd_result.process.returncode != 0:
                LOG.info(cmd_stdout)
                LOG.error(cmd_stderr)

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


REGULAR_STACK_FUNCTION_LIST = [
    "ApiGwFunction",
    "SfnFunction",
]
REGULAR_STACK_APIGW_LIST = [
    "HelloWorldServerlessApi",
]
REGULAR_STACK_SFN_LIST = [
    "MyStateMachine",
]


class TestLogsCommandWithRegularStack(LogsIntegTestCases):
    test_template_folder = "python-apigw-sfn"

    @parameterized.expand(REGULAR_STACK_FUNCTION_LIST)
    def test_function_logs(self, function_name: str):
        self._test_function_logs(function_name)

    @parameterized.expand(REGULAR_STACK_FUNCTION_LIST)
    def test_tail(self, function_name: str):
        self._test_tail(function_name)

    @parameterized.expand(REGULAR_STACK_FUNCTION_LIST)
    def test_filter(self, function_name: str):
        self._test_filter(function_name)

    @parameterized.expand(itertools.product(REGULAR_STACK_APIGW_LIST, ["hello", "world"]))
    def test_apigw_logs(self, apigw_name: str, path: str):
        self._test_apigw_logs(apigw_name, path)

    @parameterized.expand(REGULAR_STACK_SFN_LIST)
    def test_sfn_logs(self, state_machine_name: str):
        self._test_sfn_logs(state_machine_name)

    @parameterized.expand(itertools.product(REGULAR_STACK_APIGW_LIST, ["hello"]))
    def test_end_to_end_apigw(self, apigw_name: str, path: str):
        self._test_end_to_end_apigw(apigw_name, path)

    @parameterized.expand(itertools.product(REGULAR_STACK_APIGW_LIST, ["world"]))
    def test_end_to_end_sfn(self, apigw_name: str, path: str):
        self._test_end_to_end_sfn(apigw_name, path)

    @parameterized.expand(itertools.product(REGULAR_STACK_FUNCTION_LIST, [None, "text", "json"]))
    def test_output(self, function_name: str, output: Optional[str]):
        self._test_output(function_name, output)

    @parameterized.expand(
        itertools.product(
            REGULAR_STACK_FUNCTION_LIST,
            [
                (None, None, True),
                (None, "1 minute", True),
                ("1 minute", None, True),
                ("now", None, False),
            ],
        )
    )
    def test_start_end(self, function_name: str, start_end_time_params: Tuple[Optional[str], Optional[str], bool]):
        self._test_start_end(function_name, start_end_time_params)

    @parameterized.expand(REGULAR_STACK_FUNCTION_LIST)
    def test_include_traces(self, function_name: str):
        self._test_include_traces(function_name)


NESTED_STACK_FUNCTION_LIST = [
    "ApiGwFunction",
    "SfnFunction",
    "ChildStack/ApiGwFunction",
    "ChildStack/SfnFunction",
    "ChildStack/GrandChildStack/ApiGwFunction",
    "ChildStack/GrandChildStack/SfnFunction",
]
NESTED_STACK_APIGW_LIST = [
    "HelloWorldServerlessApi",
    "ChildStack/HelloWorldServerlessApi",
    "ChildStack/GrandChildStack/HelloWorldServerlessApi",
]
NESTED_STACK_SFN_LIST = [
    "MyStateMachine",
    "ChildStack/MyStateMachine",
    "ChildStack/GrandChildStack/MyStateMachine",
]


class TestLogsCommandWithNestedStack(LogsIntegTestCases):
    test_template_folder = "nested-python-apigw-sfn"

    @parameterized.expand(NESTED_STACK_FUNCTION_LIST)
    def test_function_logs(self, function_name: str):
        self._test_function_logs(function_name)

    @parameterized.expand(NESTED_STACK_FUNCTION_LIST)
    def test_tail(self, function_name: str):
        self._test_tail(function_name)

    @parameterized.expand(NESTED_STACK_FUNCTION_LIST)
    def test_filter(self, function_name: str):
        self._test_filter(function_name)

    @parameterized.expand(itertools.product(NESTED_STACK_APIGW_LIST, ["hello", "world"]))
    def test_apigw_logs(self, apigw_name: str, path: str):
        self._test_apigw_logs(apigw_name, path)

    @parameterized.expand(NESTED_STACK_SFN_LIST)
    def test_sfn_logs(self, state_machine_name: str):
        self._test_sfn_logs(state_machine_name)

    @parameterized.expand(itertools.product(NESTED_STACK_APIGW_LIST, ["hello"]))
    def test_end_to_end_apigw(self, apigw_name: str, path: str):
        self._test_end_to_end_apigw(apigw_name, path)

    @parameterized.expand(itertools.product(NESTED_STACK_APIGW_LIST, ["world"]))
    def test_end_to_end_sfn(self, apigw_name: str, path: str):
        self._test_end_to_end_sfn(apigw_name, path)

    @parameterized.expand(itertools.product(NESTED_STACK_FUNCTION_LIST, [None, "text", "json"]))
    def test_output(self, function_name: str, output: Optional[str]):
        self._test_output(function_name, output)

    @parameterized.expand(
        itertools.product(
            NESTED_STACK_FUNCTION_LIST,
            [
                (None, None, True),
                (None, "1 minute", True),
                ("1 minute", None, True),
                ("now", None, False),
            ],
        )
    )
    def test_start_end(self, function_name: str, start_end_time_params: Tuple[Optional[str], Optional[str], bool]):
        self._test_start_end(function_name, start_end_time_params)

    @parameterized.expand(NESTED_STACK_FUNCTION_LIST)
    def test_include_traces(self, function_name: str):
        self._test_include_traces(function_name)
