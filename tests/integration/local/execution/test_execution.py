"""Integration tests for sam local execution commands - edge cases only."""

from pathlib import Path
from parameterized import parameterized

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.integration.durable_integ_base import DurableIntegBase
from tests.integration.durable_function_examples import DurableFunctionExamples
from tests.testing_utils import run_command


class TestLocalExecution(DurableIntegBase, InvokeIntegBase):
    template = Path("template.yaml")
    template_subdir = "durable"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.build_durable_functions()

    @parameterized.expand(
        [
            ("get", "GetDurableExecution"),
            ("history", "GetDurableExecutionHistory"),
            ("stop", "StopDurableExecution"),
        ]
    )
    def test_execution_nonexistent_execution(self, command, operation_name):
        """Test execution command when execution does not exist."""
        nonexistent_arn = "00000000-0000-0000-0000-000000000000"
        command_list = [self.cmd, "local", "execution", command, nonexistent_arn]

        result = run_command(command_list)
        stderr_str = result.stderr.decode("utf-8") if isinstance(result.stderr, bytes) else result.stderr

        self.assertNotEqual(result.process.returncode, 0)
        expected_message = f"Error: An error occurred (404) when calling the {operation_name} operation: Execution {nonexistent_arn} not found\n"
        self.assertEqual(stderr_str, expected_message)

    def test_execution_stop_already_completed(self):
        """Test execution stop on already completed execution."""
        example = DurableFunctionExamples.HELLO_WORLD
        execution_name = f"{example.function_name.lower()}-stop-test"

        # Invoke and complete the execution
        command_list = self.get_invoke_command_list(
            example.function_name, no_event=True, durable_execution_name=execution_name
        )
        result = run_command(command_list)
        stdout_str = result.stdout.decode("utf-8") if isinstance(result.stdout, bytes) else result.stdout
        self.assertEqual(result.process.returncode, 0)

        # Extract execution ARN
        execution_arn = self.assert_invoke_output(stdout_str, input_data={}, execution_name=execution_name)

        # Try to stop already completed execution
        stop_command = [self.cmd, "local", "execution", "stop", execution_arn]
        result = run_command(stop_command)
        stderr_str = result.stderr.decode("utf-8") if isinstance(result.stderr, bytes) else result.stderr

        self.assertNotEqual(result.process.returncode, 0)
        expected_message = f"Error: An error occurred (409) when calling the StopDurableExecution operation: Execution {execution_arn} is already completed\n"
        self.assertEqual(stderr_str, expected_message)
