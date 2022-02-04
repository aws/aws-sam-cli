import time
from pathlib import Path
from unittest import skipIf

import boto3
from tests.integration.traces.traces_integ_base import TracesIntegBase, RETRY_COUNT
from tests.testing_utils import run_command, RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from datetime import datetime
import logging
from parameterized import parameterized

LOG = logging.getLogger(__name__)

SKIP_TRACES_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_TRACES_TESTS, "Skip traces tests in CI/CD only")
class TestTracesCommand(TracesIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.lambda_client = boto3.client("lambda")
        cls.cfn_client = boto3.client("cloudformation")
        cls.xray_client = boto3.client("xray")

        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "traces")

        cls.stack_name = cls._method_to_stack_name("test.integration.test_traces_command")

        LOG.info("Deploying stack %s", cls.stack_name)

        deploy_cmd = cls.get_basic_deploy_command_list(
            stack_name=cls.stack_name,
            template_file=cls.test_data_path.joinpath("python-apigw-sfn", "template.yaml"),
            resolve_s3=True,
            capabilities="CAPABILITY_IAM",
        )
        deploy_result = run_command(deploy_cmd)

        if deploy_result.process.returncode != 0:
            LOG.error(f"Deployment of the test stack is failed with {deploy_result.stderr}")

        cls.stack_resources = cls.cfn_client.describe_stack_resources(StackName=cls.stack_name).get(
            "StackResources", []
        )

    @classmethod
    def tearDownClass(cls):
        cls.cfn_client.delete_stack(StackName=cls.stack_name)

    def _get_physical_id(self, logical_id: str):
        for stack_resource in self.stack_resources:
            if stack_resource["LogicalResourceId"] == logical_id:
                return stack_resource["PhysicalResourceId"]

        return None

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_function_traces(self, function_name):
        function_id = self._get_physical_id(function_name)
        expected_trace_output = [function_id]

        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=function_id)
        LOG.info("Lambda invoke result %s", lambda_invoke_result)
        cmd_list = self.get_traces_command_list(beta_features=True)
        self._check_traces(cmd_list, expected_trace_output)

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_trace_id(self, function_name):
        function_id = self._get_physical_id(function_name)
        expected_trace_output = [function_id]

        start_time = datetime.utcnow()
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=function_id)
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        for _ in range(RETRY_COUNT):
            end_time = datetime.utcnow()
            kwargs = {"TimeRangeType": "TraceId", "StartTime": start_time, "EndTime": end_time}
            trace_summaries_response = self.xray_client.get_trace_summaries(**kwargs)
            trace_summaries = trace_summaries_response.get("TraceSummaries", [])
            if trace_summaries:
                break
            time.sleep(2)

        if not trace_summaries:
            self.fail("can't find any trace summaries")

        trace_id = trace_summaries[0].get("Id")
        LOG.info("Trace id: %s", trace_id)

        cmd_list = self.get_traces_command_list(trace_id=trace_id, beta_features=True)
        self._check_traces(cmd_list, expected_trace_output, has_service_graph=False)

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_trace_start_time(self, function_name):
        function_id = self._get_physical_id(function_name)
        expected_trace_output = [function_id]

        start_time = datetime.utcnow()
        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=function_id)
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_traces_command_list(start_time=str(start_time), beta_features=True)
        self._check_traces(cmd_list, expected_trace_output)

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_trace_end_time(self, function_name):
        function_id = self._get_physical_id(function_name)
        expected_trace_output = [function_id]

        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=function_id)
        LOG.info("Lambda invoke result %s", lambda_invoke_result)
        end_time = datetime.utcnow()

        cmd_list = self.get_traces_command_list(end_time=str(end_time), beta_features=True)
        self._check_traces(cmd_list, expected_trace_output)

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_traces_with_tail(self, function_name):
        function_id = self._get_physical_id(function_name)
        expected_trace_output = [function_id]

        LOG.info("Invoking function %s", "HelloWorldFunction")
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=function_id)
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_traces_command_list(tail=True, beta_features=True)
        tail_read_thread = self.start_tail(cmd_list, expected_trace_output)
        while tail_read_thread.is_alive():
            time.sleep(1)

    @parameterized.expand([("ApiGwFunction",), ("SfnFunction",)])
    def test_traces_with_unformatted(self, function_name):
        function_id = self._get_physical_id(function_name)
        expected_trace_output = [function_id]

        LOG.info("Invoking function %s", function_name)
        lambda_invoke_result = self.lambda_client.invoke(FunctionName=function_id)
        LOG.info("Lambda invoke result %s", lambda_invoke_result)

        cmd_list = self.get_traces_command_list(unformatted=True, beta_features=True)
        self._check_traces(cmd_list, expected_trace_output, output="JSON")

    def _check_traces(self, cmd_list, trace_strings, output="TEXT", has_service_graph=True):
        for _ in range(RETRY_COUNT):
            cmd_result = run_command(cmd_list)
            self.assertEqual(cmd_result.process.returncode, 0)

            actual_output = cmd_result.stdout.decode("utf-8")

            if has_service_graph and not self._check_traces_with_service_graph(trace_strings, actual_output, output):
                time.sleep(2)
                continue
            if not self._check_traces_with_xray_event(trace_strings, actual_output, output):
                time.sleep(2)
                continue
            return

        self.fail(f"No match found for one of the expected trace outputs '{trace_strings}'")

    def _check_traces_with_service_graph(self, trace_strings, console_output, output="TEXT"):
        if output == "TEXT":
            return self._check_service_graph_with_output_text(trace_strings, console_output)
        if output == "JSON":
            return self._check_service_graph_with_output_json(trace_strings, console_output)

    def _check_traces_with_xray_event(self, trace_strings, console_output, output="TEXT"):
        if output == "TEXT":
            return self._check_xray_event_with_output_text(trace_strings, console_output)
        if output == "JSON":
            return self._check_xray_event_with_output_json(trace_strings, console_output)

    def _check_xray_event_with_output_text(self, trace_strings, console_output):
        # It's hard to verify the entire text output, just verify if some keywords exist and verify if expected
        # trace strings exist in the console output as well
        if "XRay Event" not in console_output:
            return False
        return self._check_trace_string_exist(trace_strings, console_output)

    def _check_xray_event_with_output_json(self, trace_strings, console_output):
        # It's hard to verify the entire json output, just verify if some keywords exist and verify if expected
        # trace strings exist in the console output as well
        if 'content-type": "application/json' not in console_output:
            return False
        return self._check_trace_string_exist(trace_strings, console_output)

    def _check_service_graph_with_output_text(self, trace_strings, console_output):
        # It's hard to verify the entire text output, just verify if some keywords exist and verify if expected
        # trace strings exist in the console output as well
        if "New XRay Service Graph" not in console_output:
            return False
        if "Start time" not in console_output:
            return False
        if "End time" not in console_output:
            return False
        if "Reference Id" not in console_output:
            return False
        if "Summary_statistics" not in console_output:
            return False
        return self._check_trace_string_exist(trace_strings, console_output)

    def _check_service_graph_with_output_json(self, trace_strings, console_output):
        # It's hard to verify the entire json output, just verify if some keywords exist and verify if expected
        # trace strings exist in the console output
        if "Segments" not in console_output:
            return False
        if "trace_id" not in console_output:
            return False
        return self._check_trace_string_exist(trace_strings, console_output)

    @staticmethod
    def _check_trace_string_exist(trace_strings, console_output):
        for trace_string in trace_strings:
            if trace_string not in console_output:
                return False
        return True
