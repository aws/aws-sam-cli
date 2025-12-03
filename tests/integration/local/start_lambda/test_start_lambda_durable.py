"""Integration tests for sam local start-lambda with durable functions."""

import json
import shutil
import time
import json
import pytest
import boto3
from pathlib import Path
from botocore import UNSIGNED
from botocore.config import Config
from parameterized import parameterized

from tests.integration.local.start_lambda.start_lambda_api_integ_base import StartLambdaIntegBaseClass
from tests.integration.durable_integ_base import DurableIntegBase
from tests.integration.durable_function_examples import DurableFunctionExamples

from tests.testing_utils import (
    get_sam_command,
)


class TestStartLambdaDurable(DurableIntegBase, StartLambdaIntegBaseClass):
    container_host_interface = "0.0.0.0"
    collect_start_lambda_process_output = True

    @classmethod
    def setUpClass(cls):
        """Set up test class with SDK path configuration."""
        cls.test_data_path = Path(cls.integration_dir, "testdata")
        cls.template_path = str(Path(cls.test_data_path, "durable", "template.yaml"))
        cls.build_durable_functions()

        # Update template_path to point to built template (relative to integration_dir)
        cls.template_path = "/" + str(cls.built_template_path.relative_to(cls.integration_dir))
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        build_dir = Path(cls.working_dir, ".aws-sam")
        shutil.rmtree(build_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    def assert_durable_invoke_response(self, response, example, invocation_type="RequestResponse"):
        """Assert durable function invoke response and return execution ARN."""
        expected_status_code = 202 if invocation_type == "Event" else 200
        self.assertEqual(response.get("StatusCode"), expected_status_code)
        self.assertIsNone(response.get("FunctionError"))

        response_metadata = response.get("ResponseMetadata", {})
        headers = response_metadata.get("HTTPHeaders", {})
        execution_arn = headers.get("x-amz-durable-execution-arn")

        self.assertIsNotNone(execution_arn, f"Expected durable execution ARN header in: {headers}")
        self.assertTrue(len(execution_arn) > 0)

        if invocation_type == "RequestResponse":
            payload_obj = response.get("Payload")
            payload = payload_obj.read().decode("utf-8") if payload_obj else ""

            expected_response = example.get_expected_response(self.test_data_path)
            if expected_response:
                self.assertEqual(
                    payload, expected_response, f"Expected payload to match ExecutionSucceededDetails.Result.Payload"
                )
        else:
            # Event invocations should have empty payload
            payload_obj = response.get("Payload")
            payload = payload_obj.read().decode("utf-8") if payload_obj else ""
            self.assertEqual(payload, "", "Expected empty payload for async Event invocations")

        return execution_arn

    def wait_for_pending_callback(self, execution_arn, max_wait=30):
        """Wait for execution to have a pending callback (CallbackStarted event)."""
        for _ in range(max_wait):
            history_response = self.lambda_client.get_durable_execution_history(
                DurableExecutionArn=execution_arn, IncludeExecutionData=True
            )
            callback_id = self.get_callback_id_from_history(history_response.get("Events", []))
            if callback_id:
                return callback_id
            time.sleep(1)
        return None

    def wait_for_execution_status(self, execution_arn, expected_status, max_wait=30):
        """Wait for execution to reach expected status."""
        for _ in range(max_wait):
            execution_response = self.lambda_client.get_durable_execution(DurableExecutionArn=execution_arn)
            if execution_response.get("Status") == expected_status:
                return execution_response
            time.sleep(1)
        return execution_response

    def invoke_and_wait_for_callback(self, payload=None):
        """Helper to invoke WaitForCallback function and wait for callback to be pending.

        Returns:
            tuple: (execution_arn, callback_id)
        """
        if payload:
            response = self.lambda_client.invoke(
                FunctionName="WaitForCallback", InvocationType="Event", Payload=payload
            )
        else:
            response = self.lambda_client.invoke(FunctionName="WaitForCallback", InvocationType="Event")

        execution_arn = self.assert_durable_invoke_response(
            response, DurableFunctionExamples.WAIT_FOR_CALLBACK, invocation_type="Event"
        )
        callback_id = self.wait_for_pending_callback(execution_arn)
        self.assertIsNotNone(callback_id, "Expected to find callback ID in history")

        execution_response = self.lambda_client.get_durable_execution(DurableExecutionArn=execution_arn)
        self.assertEqual(execution_response.get("Status"), "RUNNING")

        return execution_arn, callback_id

    @parameterized.expand(
        [
            (DurableFunctionExamples.HELLO_WORLD, "RequestResponse"),
            (DurableFunctionExamples.HELLO_WORLD, "Event"),
            (DurableFunctionExamples.NAMED_STEP, "RequestResponse"),
            (DurableFunctionExamples.NAMED_STEP, "Event"),
            (DurableFunctionExamples.NAMED_WAIT, "RequestResponse"),
            (DurableFunctionExamples.NAMED_WAIT, "Event"),
            (DurableFunctionExamples.MAP_OPERATIONS, "RequestResponse"),
            (DurableFunctionExamples.MAP_OPERATIONS, "Event"),
            (DurableFunctionExamples.PARALLEL, "RequestResponse"),
            (DurableFunctionExamples.PARALLEL, "Event"),
        ],
        name_func=DurableIntegBase.parameterized_test_name,
    )
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_start_lambda_invoke_durable_function(self, example, invocation_type):
        """Test start-lambda with durable functions."""
        execution_name = f"{example.function_name.lower()}-integration-test"
        kwargs = {"FunctionName": example.function_name, "DurableExecutionName": execution_name}
        if invocation_type == "Event":
            kwargs["InvocationType"] = "Event"

        response = self.lambda_client.invoke(**kwargs)
        execution_arn = self.assert_durable_invoke_response(response, example, invocation_type=invocation_type)

        if invocation_type == "Event":
            max_wait = 30
            for _ in range(max_wait):
                execution_response = self.lambda_client.get_durable_execution(DurableExecutionArn=execution_arn)
                if execution_response.get("Status") == "SUCCEEDED":
                    break
                time.sleep(1)
        else:
            execution_response = self.lambda_client.get_durable_execution(DurableExecutionArn=execution_arn)

        self.assertEqual(execution_response.get("Status"), "SUCCEEDED")

    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_start_lambda_invoke_timeout(self):
        """Test start-lambda with durable function execution timeout."""
        example = DurableFunctionExamples.EXECUTION_TIMEOUT
        execution_name = "executiontimeout-integration-test"
        event_data = {"wait_seconds": 30}

        response = self.lambda_client.invoke(
            FunctionName=example.function_name,
            DurableExecutionName=execution_name,
            Payload=json.dumps(event_data).encode("utf-8"),
        )

        self.assertEqual(response.get("StatusCode"), 200)
        execution_arn = response["ResponseMetadata"]["HTTPHeaders"]["x-amz-durable-execution-arn"]
        self.assertIsNotNone(execution_arn)

        # Check execution status - should timeout
        execution_response = self.lambda_client.get_durable_execution(DurableExecutionArn=execution_arn)
        self.assertEqual(execution_response.get("Status"), "TIMED_OUT")

        history_response = self.lambda_client.get_durable_execution_history(
            DurableExecutionArn=execution_arn, IncludeExecutionData=True
        )

        self.assert_execution_history(history_response, example)

    @parameterized.expand(
        [
            ("with_result", '"callback_result"'),
            ("without_result", None),
        ]
    )
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_start_lambda_invoke_wait_for_callback_success_http(self, name, result):
        """Test start-lambda with wait_for_callback success cases via HTTP API."""
        execution_arn, callback_id = self.invoke_and_wait_for_callback()

        if result:
            self.lambda_client.send_durable_execution_callback_success(CallbackId=callback_id, Result=result)
        else:
            self.lambda_client.send_durable_execution_callback_success(CallbackId=callback_id)

        execution_response = self.wait_for_execution_status(execution_arn, "SUCCEEDED")
        self.assertEqual(execution_response.get("Status"), "SUCCEEDED")

        # Verify execution history
        history_response = self.lambda_client.get_durable_execution_history(
            DurableExecutionArn=execution_arn, IncludeExecutionData=True
        )
        self.assert_execution_history(history_response, DurableFunctionExamples.WAIT_FOR_CALLBACK)

    @parameterized.expand(
        [
            (
                "all_parameters",
                {
                    "ErrorData": '{"detail": "test error"}',
                    "StackTrace": ["line1", "line2"],
                    "ErrorType": "TestError",
                    "ErrorMessage": "Test error message",
                },
            ),
            ("minimal_parameters", {}),
            ("error_message_only", {"ErrorMessage": "Simple error message"}),
        ]
    )
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_start_lambda_invoke_wait_for_callback_failure_http(self, name, error_params):
        """Test start-lambda with wait_for_callback failure cases via HTTP API."""
        execution_arn, callback_id = self.invoke_and_wait_for_callback()

        self.lambda_client.send_durable_execution_callback_failure(CallbackId=callback_id, Error=error_params)

        execution_response = self.wait_for_execution_status(execution_arn, "FAILED")
        self.assertEqual(execution_response.get("Status"), "FAILED")

        history_response = self.lambda_client.get_durable_execution_history(
            DurableExecutionArn=execution_arn, IncludeExecutionData=True
        )
        self.assert_execution_history(history_response, DurableFunctionExamples.WAIT_FOR_CALLBACK_FAILURE)

    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_start_lambda_invoke_wait_for_callback_timeout(self):
        """Test start-lambda with wait_for_callback timeout (no callback sent)."""
        # Set a short timeout so test doesn't take too long
        event_payload = json.dumps({"timeout_seconds": 5, "heartbeat_timeout_seconds": 3})

        execution_arn, callback_id = self.invoke_and_wait_for_callback(payload=event_payload)

        # Don't send any callback - let it timeout
        execution_response = self.wait_for_execution_status(execution_arn, "FAILED", max_wait=15)
        self.assertEqual(execution_response.get("Status"), "FAILED")

        # Verify timeout events in execution history
        history_response = self.lambda_client.get_durable_execution_history(
            DurableExecutionArn=execution_arn, IncludeExecutionData=True
        )
        callback_timed_out = self.get_event_from_history(history_response.get("Events", []), "CallbackTimedOut")
        self.assertIsNotNone(callback_timed_out, "Expected CallbackTimedOut event in history")

        execution_failed = self.get_event_from_history(history_response.get("Events", []), "ExecutionFailed")
        self.assertIsNotNone(execution_failed, "Expected ExecutionFailed event in history")

    @parameterized.expand(
        [
            ("with_result", {"result": '"callback_result"'}),
            ("without_result", {}),
        ]
    )
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_start_lambda_invoke_wait_for_callback_success_cli(self, name, kwargs):
        """Test start-lambda with wait_for_callback success via CLI command."""
        execution_arn, callback_id = self.invoke_and_wait_for_callback()

        cmd = self.get_callback_command_list("succeed", callback_id, **kwargs)

        stdout, stderr, return_code = self.run_command_with_logging(cmd, f"callback_succeed_{name}")
        self.assertEqual(return_code, 0, "Callback CLI command should succeed")
        self.assertIn("Callback success sent", stdout)

        execution_response = self.wait_for_execution_status(execution_arn, "SUCCEEDED")
        self.assertEqual(execution_response.get("Status"), "SUCCEEDED")

        history_response = self.lambda_client.get_durable_execution_history(
            DurableExecutionArn=execution_arn, IncludeExecutionData=True
        )
        self.assert_execution_history(history_response, DurableFunctionExamples.WAIT_FOR_CALLBACK)

    @parameterized.expand(
        [
            (
                "all_parameters",
                [
                    "--error-data",
                    '{"detail": "test error"}',
                    "--stack-trace",
                    "line1",
                    "--stack-trace",
                    "line2",
                    "--error-type",
                    "TestError",
                    "--error-message",
                    "Test error message",
                ],
            ),
            ("minimal_parameters", []),
            ("error_message_only", ["--error-message", "Simple error message"]),
        ]
    )
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_callback_cli_fail(self, name, cli_args):
        """Test sam local callback fail CLI command."""
        execution_arn, callback_id = self.invoke_and_wait_for_callback()

        # Use CLI command instead of Lambda client
        cmd = [get_sam_command(), "local", "callback", "fail", callback_id] + cli_args

        stdout, stderr, return_code = self.run_command_with_logging(cmd, f"callback_fail_{name}")
        self.assertEqual(return_code, 0, "Callback CLI command should succeed")
        self.assertIn("Callback failure sent", stdout)

        execution_response = self.wait_for_execution_status(execution_arn, "FAILED")
        self.assertEqual(execution_response.get("Status"), "FAILED")

        history_response = self.lambda_client.get_durable_execution_history(
            DurableExecutionArn=execution_arn, IncludeExecutionData=True
        )
        self.assert_execution_history(history_response, DurableFunctionExamples.WAIT_FOR_CALLBACK_FAILURE)

    @pytest.mark.timeout(timeout=300, method="thread")
    def test_local_callback_cli_heartbeat(self):
        """Test sam local callback heartbeat CLI command."""
        event_payload = json.dumps({"timeout_seconds": 60, "heartbeat_timeout_seconds": 30})
        execution_arn, callback_id = self.invoke_and_wait_for_callback(payload=event_payload)

        # Send heartbeat via CLI
        cmd = self.get_callback_command_list("heartbeat", callback_id)
        stdout, stderr, return_code = self.run_command_with_logging(cmd, "callback_heartbeat")
        self.assertEqual(return_code, 0, "Heartbeat CLI command should succeed")

        # Send success via CLI
        cmd = self.get_callback_command_list("succeed", callback_id)
        stdout, stderr, return_code = self.run_command_with_logging(cmd, "callback_succeed")
        self.assertEqual(return_code, 0, "Success CLI command should succeed")

        execution_response = self.wait_for_execution_status(execution_arn, "SUCCEEDED")
        self.assertEqual(execution_response.get("Status"), "SUCCEEDED")

        history_response = self.lambda_client.get_durable_execution_history(
            DurableExecutionArn=execution_arn, IncludeExecutionData=True
        )
        self.assert_execution_history(history_response, DurableFunctionExamples.WAIT_FOR_CALLBACK)
