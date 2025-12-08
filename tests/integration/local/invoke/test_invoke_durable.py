import json
from pathlib import Path

from parameterized import parameterized

from tests.integration.durable_integ_base import DurableIntegBase
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.integration.durable_function_examples import DurableFunctionExamples


# Assertions are inherited from DurableIntegBase, invoke set up gets inherited from InvokeIntegBase
class TestInvokeDurable(DurableIntegBase, InvokeIntegBase):
    template = Path("template.yaml")
    template_subdir = "durable"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.build_durable_functions()

    @parameterized.expand(
        [
            (DurableFunctionExamples.HELLO_WORLD,),
            (DurableFunctionExamples.NAMED_STEP,),
            (DurableFunctionExamples.NAMED_WAIT,),
            (DurableFunctionExamples.MAP_OPERATIONS,),
            (DurableFunctionExamples.PARALLEL,),
        ],
        name_func=DurableIntegBase.parameterized_test_name,
    )
    def test_local_invoke_durable_function(self, example):
        """Test durable function invocation."""
        execution_name = f"{example.function_name.lower()}-integration-test"
        command_list = self.get_invoke_command_list(
            example.function_name, no_event=True, durable_execution_name=execution_name
        )

        stdout, stderr, invoke_return_code = self.run_command_with_logging(
            command_list, f"test_local_invoke_durable_function_{example.function_name}"
        )

        self.assertEqual(invoke_return_code, 0)

        # Assert invoke output and get execution ARN
        execution_arn = self.assert_invoke_output(stdout, input_data={}, execution_name=execution_name)

        if not example.skip_history_assertions:
            # Get and verify execution history
            history_command = self.get_execution_history_command_list(execution_arn)
            history_stdout, history_stderr, history_return_code = self.run_command(history_command)
            self.assertEqual(history_return_code, 0)

            # Assert the execution history matches the expected history
            self.assert_execution_history(json.loads(history_stdout), example)

    def test_local_invoke_durable_function_timeout(self):
        """Test durable function execution timeout with 30-second wait and 5-second timeout."""
        example = DurableFunctionExamples.EXECUTION_TIMEOUT
        function_name = example.function_name
        execution_name = "executiontimeout-integration-test"
        event_path = str(self.test_data_path / "durable" / "events" / "timeout_test_event.json")

        command_list = self.get_invoke_command_list(
            function_name, event_path=event_path, durable_execution_name=execution_name
        )

        stdout, stderr, invoke_return_code = self.run_command_with_logging(
            command_list, f"test_local_invoke_durable_function_{function_name}"
        )

        self.assertEqual(invoke_return_code, 0)

        # Assert invoke output shows timeout
        execution_arn = self.assert_invoke_output(
            stdout, input_data={"wait_seconds": 30}, execution_name=execution_name, expected_status="TIMED_OUT"
        )

        # Get and verify execution history
        history_command = self.get_execution_history_command_list(execution_arn)
        history_stdout, history_stderr, history_return_code = self.run_command(history_command)
        self.assertEqual(history_return_code, 0)

        # Assert the execution history matches the expected history
        self.assert_execution_history(json.loads(history_stdout), example)

    @parameterized.expand(
        [
            ("with_result", '"callback_result"'),
            ("without_result", None),
        ]
    )
    def test_local_invoke_durable_function_wait_for_callback(self, name, result):
        """Test durable function with wait_for_callback operation."""
        command_list = self.get_invoke_command_list("WaitForCallback", no_event=True)
        process, output_lines, thread = self.start_command_with_streaming(command_list, "invoke_wait_for_callback")

        callback_id = self.wait_for_callback_id(output_lines)
        self.assertIsNotNone(callback_id, "Callback ID not found in output")

        # Send callback success via CLI
        if result:
            callback_command = self.get_callback_command_list("succeed", callback_id, result=result)
        else:
            callback_command = self.get_callback_command_list("succeed", callback_id)

        callback_stdout, callback_stderr, callback_return_code = self.run_command_with_logging(
            callback_command, "send_callback_success"
        )

        # Assert callback command succeeded
        self.assertEqual(callback_return_code, 0, f"Callback failed: {callback_stdout}\n{callback_stderr}")
        self.assertIn("Callback success sent", callback_stdout)
        self.assertIn(callback_id, callback_stdout)

        # Wait for invoke process to complete
        stdout, _ = process.communicate(timeout=30)
        output_lines.append(stdout)
        self.assertEqual(process.returncode, 0)

        # Assert invoke output and get execution ARN
        full_output = "".join(output_lines)
        self.assertIn("Waiting for callback:", full_output)
        self.assertIn("Status:   SUCCEEDED", full_output)

        execution_arn = self.assert_invoke_output(full_output, input_data={})

        # Get and verify execution history
        history_command = self.get_execution_history_command_list(execution_arn)
        history_stdout, history_stderr, history_return_code = self.run_command(history_command)
        self.assertEqual(history_return_code, 0)

        self.assert_execution_history(json.loads(history_stdout), DurableFunctionExamples.WAIT_FOR_CALLBACK)

    @parameterized.expand(
        [
            (
                "all_parameters",
                {"error_type": "TestError", "error_message": "Test failure", "error_data": "Test cause"},
            ),
            ("minimal", {"error_message": "Test failure"}),
            ("error_only", {"error_message": "Error"}),
        ]
    )
    def test_local_invoke_callback_fail(self, name, kwargs):
        """Test callback failure via CLI."""
        command_list = self.get_invoke_command_list("WaitForCallback", no_event=True)
        process, output_lines, thread = self.start_command_with_streaming(
            command_list, f"invoke_wait_for_callback_fail_{name}"
        )

        callback_id = self.wait_for_callback_id(output_lines)
        self.assertIsNotNone(callback_id)

        # Send callback failure
        callback_command = self.get_callback_command_list("fail", callback_id, **kwargs)
        callback_stdout, callback_stderr, callback_return_code = self.run_command_with_logging(
            callback_command, f"callback_fail_{name}"
        )

        self.assertEqual(callback_return_code, 0)

        stdout, _ = process.communicate(timeout=30)
        output_lines.append(stdout)
        self.assertEqual(process.returncode, 0)

        full_output = "".join(output_lines)
        self.assertIn("Status:   FAILED", full_output)

    def test_local_invoke_callback_heartbeat(self):
        """Test callback heartbeat via CLI."""
        event_file = str(self.test_data_path / "durable" / "events" / "callback_heartbeat.json")
        command_list = self.get_invoke_command_list("WaitForCallback", event_path=event_file)
        process, output_lines, thread = self.start_command_with_streaming(
            command_list, "invoke_wait_for_callback_heartbeat"
        )

        callback_id = self.wait_for_callback_id(output_lines)
        self.assertIsNotNone(callback_id)

        # Send heartbeat
        heartbeat_command = self.get_callback_command_list("heartbeat", callback_id)
        heartbeat_stdout, heartbeat_stderr, heartbeat_return_code = self.run_command_with_logging(
            heartbeat_command, "callback_heartbeat"
        )
        self.assertEqual(heartbeat_return_code, 0)

        # Send success
        success_command = self.get_callback_command_list("succeed", callback_id)
        success_stdout, success_stderr, success_return_code = self.run_command_with_logging(
            success_command, "callback_succeed"
        )
        self.assertEqual(success_return_code, 0)

        stdout, _ = process.communicate(timeout=30)
        output_lines.append(stdout)
        self.assertEqual(process.returncode, 0)

        full_output = "".join(output_lines)
        self.assertIn("Status:   SUCCEEDED", full_output)
