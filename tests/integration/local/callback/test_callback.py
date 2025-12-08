"""Integration tests for sam local callback commands - edge cases only."""

import re
from pathlib import Path
from parameterized import parameterized

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.integration.durable_integ_base import DurableIntegBase
from tests.integration.durable_function_examples import DurableFunctionExamples
from tests.testing_utils import run_command


class TestLocalCallback(DurableIntegBase, InvokeIntegBase):
    template = Path("template.yaml")
    template_subdir = "durable"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.build_durable_functions()

    @parameterized.expand(
        [
            ("succeed", "SendDurableExecutionCallbackSuccess", "success", "is not in STARTED state"),
            ("fail", "SendDurableExecutionCallbackFailure", "failure", "is not in STARTED state"),
            ("heartbeat", "SendDurableExecutionCallbackHeartbeat", "heartbeat", "is not active"),
        ]
    )
    def test_callback_already_completed_execution(self, action, operation_name, callback_type, error_suffix):
        """Test callback on already completed execution."""
        example = DurableFunctionExamples.WAIT_FOR_CALLBACK
        execution_name = f"{example.function_name.lower()}-callback-test"

        # Start the execution with callback
        command_list = self.get_invoke_command_list(
            example.function_name, no_event=True, durable_execution_name=execution_name
        )
        process, output_lines, thread = self.start_command_with_streaming(
            command_list, f"test_callback_already_completed_{action}"
        )

        # Wait for callback ID
        callback_id = self.wait_for_callback_id(output_lines)
        self.assertIsNotNone(callback_id, "Failed to get callback ID from output")

        # Send first callback to complete the execution
        succeed_command = self.get_callback_command_list("succeed", callback_id, result="test result")
        result = run_command(succeed_command)
        self.assertEqual(result.process.returncode, 0)

        # Wait for process to complete
        process.wait(timeout=30)
        thread.join(timeout=5)

        # Try to send another callback (should fail)
        second_command = self.get_callback_command_list(action, callback_id)
        result = run_command(second_command)
        stderr_str = result.stderr.decode("utf-8") if isinstance(result.stderr, bytes) else result.stderr

        self.assertNotEqual(result.process.returncode, 0)
        expected_pattern = f"Error: An error occurred \\(404\\) when calling the {operation_name} operation: Failed to process callback {callback_type}: Callback .+ {error_suffix}"
        self.assertRegex(stderr_str, expected_pattern)
