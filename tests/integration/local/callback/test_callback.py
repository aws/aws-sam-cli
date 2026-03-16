"""Integration tests for sam local callback commands - edge cases only."""

import logging
import re
from pathlib import Path

import pytest
from parameterized import parameterized

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.integration.durable_integ_base import DurableIntegBase
from tests.integration.durable_function_examples import DurableFunctionExamples
from tests.testing_utils import run_command

LOG = logging.getLogger(__name__)


@pytest.mark.xdist_group(name="durable")
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
        self._do_callback_test(action, operation_name, callback_type, error_suffix)

    def _do_callback_test(self, action, operation_name, callback_type, error_suffix):
        example = DurableFunctionExamples.WAIT_FOR_CALLBACK
        execution_name = f"{example.function_name.lower()}-callback-test"

        # Start the execution with callback
        command_list = self.get_invoke_command_list(
            example.function_name, no_event=True, durable_execution_name=execution_name
        )
        LOG.info("Starting invoke command: %s", " ".join(command_list))
        process, output_lines, thread = self.start_command_with_streaming(
            command_list, f"test_callback_already_completed_{action}"
        )

        # Wait for callback ID
        LOG.info("Waiting for callback ID from streaming output...")
        callback_id = self.wait_for_callback_id(output_lines)
        LOG.info("Callback ID result: %s, output_lines collected: %d", callback_id, len(output_lines))
        if not callback_id:
            LOG.error("Failed to get callback ID. Output lines so far: %s", output_lines)
            # Also capture process state
            LOG.error("Process poll() = %s", process.poll())
        self.assertIsNotNone(callback_id, f"Failed to get callback ID from output. Lines: {output_lines}")

        # Send first callback to complete the execution
        succeed_command = self.get_callback_command_list("succeed", callback_id, result="test result")
        LOG.info("Sending first callback: %s", " ".join(succeed_command))
        result = run_command(succeed_command)
        stdout_str = result.stdout.decode("utf-8") if isinstance(result.stdout, bytes) else result.stdout
        stderr_str = result.stderr.decode("utf-8") if isinstance(result.stderr, bytes) else result.stderr
        LOG.info("First callback result: returncode=%d, stdout=%s, stderr=%s", result.process.returncode, stdout_str, stderr_str)
        self.assertEqual(result.process.returncode, 0, f"First callback failed: stdout={stdout_str}, stderr={stderr_str}")

        # Wait for process to complete and close file handles
        LOG.info("Waiting for invoke process to complete...")
        process.wait(timeout=30)
        thread.join(timeout=5)
        if process.stdin:
            process.stdin.close()
        if process.stdout:
            process.stdout.close()
        LOG.info("Invoke process completed with returncode=%d", process.returncode)

        # Try to send another callback (should fail)
        second_command = self.get_callback_command_list(action, callback_id)
        LOG.info("Sending second callback (should fail): %s", " ".join(second_command))
        result = run_command(second_command)
        stderr_str = result.stderr.decode("utf-8") if isinstance(result.stderr, bytes) else result.stderr
        stderr_str = stderr_str.replace("\r\n", "\n")
        LOG.info("Second callback result: returncode=%d, stderr=%s", result.process.returncode, stderr_str)

        self.assertNotEqual(result.process.returncode, 0)
        expected_pattern = f"Error: An error occurred \\(404\\) when calling the {operation_name} operation: Failed to process callback {callback_type}: Callback .+ {error_suffix}"
        self.assertRegex(stderr_str, expected_pattern)

    @pytest.mark.tier1_extra
    def test_tier1_callback(self):
        """Single callback test for cross-platform validation."""
        self._do_callback_test("succeed", "SendDurableExecutionCallbackSuccess", "success", "is not in STARTED state")
