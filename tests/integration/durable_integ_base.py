import json
import os
import re
import shutil
import threading
import time
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT, TimeoutExpired
from typing import Dict, Any, Optional, List
from unittest import TestCase

from tests.integration.local.invoke.invoke_integ_base import TIMEOUT
from tests.testing_utils import (
    run_command,
    get_sam_command,
    get_build_command_list,
)


class DurableIntegBase(TestCase):
    """Base class for durable function integration tests."""

    test_data_path: Path
    cmd: str
    build_dir: Path
    built_template_path: Path
    template_path: str

    @staticmethod
    def parameterized_test_name(func, num, params):
        """Generate test name for parameterized durable function tests.

        Example: test_local_invoke_durable_function_HelloWorld
        """
        return f"{func.__name__}_{params[0][0].function_name}"

    @classmethod
    def build_durable_functions(cls):
        """Run sam build for durable functions."""
        # Set environment variable for SDK .whl file location
        whl_path = Path(
            cls.test_data_path,
            "durable",
            "functions",
            "aws_durable_execution_sdk_python-1.0.0-py3-none-any.whl",
        )
        os.environ["DURABLE_SDK_WHL"] = str(whl_path.absolute())

        cls.build_dir = Path(cls.test_data_path, "durable", ".aws-sam", "build")
        cls.built_template_path = cls.build_dir / "template.yaml"

        build_command = get_build_command_list(template_path=cls.template_path, build_dir=cls.build_dir)
        result = run_command(command_list=build_command)
        if result.process.returncode != 0:
            raise RuntimeError("Build failed")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.build_dir.parent, ignore_errors=True)
        super().tearDownClass()

    def get_invoke_command_list(self, function_name, **kwargs):
        """Get command list for invoking a durable function with built template."""
        kwargs.setdefault("template_path", str(self.built_template_path))
        kwargs.setdefault("container_host_interface", "0.0.0.0")
        return self.get_command_list(function_name, **kwargs)

    def get_execution_history_command_list(self, execution_arn, output_format="json"):
        """Get command list for sam local execution history."""
        return [self.cmd, "local", "execution", "history", execution_arn, "--format", output_format]

    def get_callback_command_list(self, action, callback_id, **kwargs):
        """Get command list for sam local callback commands (succeed/fail/heartbeat)."""
        command = [get_sam_command(), "local", "callback", action, callback_id]
        if kwargs.get("result"):
            command.extend(["--result", kwargs["result"]])
        if kwargs.get("error_message"):
            command.extend(["--error-message", kwargs["error_message"]])
        if kwargs.get("error_type"):
            command.extend(["--error-type", kwargs["error_type"]])
        if kwargs.get("error_data"):
            command.extend(["--error-data", kwargs["error_data"]])
        return command

    def wait_for_callback_id(self, output_lines: List[str], timeout=30):
        """Extract callback ID from output lines, waiting up to timeout seconds."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            for line in output_lines:
                if "Waiting for callback:" in line:
                    match = re.search(r"Waiting for callback: (.+)", line)
                    if match:
                        return match.group(1).strip()
            time.sleep(0.1)
        return None

    def get_callback_id_from_history(self, history_events):
        """Extract callback ID from execution history events."""
        for event in history_events:
            if event.get("EventType") == "CallbackStarted":
                return event.get("CallbackStartedDetails", {}).get("CallbackId")
        return None

    def get_event_from_history(self, history_events, event_type):
        """Get a specific event type from execution history events."""
        for event in history_events:
            if event.get("EventType") == event_type:
                return event
        return None

    def run_command_with_logging(self, command_list, test_name, env=None, cwd=None):
        """Run command and print output with labels."""
        print(f"\n{'='*80}")
        print(f"Running: {test_name}")
        print(f"Command: {' '.join(command_list)}")
        print(f"{'='*80}\n")

        result = run_command(command_list, env=env, cwd=cwd, timeout=TIMEOUT)

        # Decode bytes to strings
        stdout_str = result.stdout.decode("utf-8") if isinstance(result.stdout, bytes) else result.stdout
        stderr_str = result.stderr.decode("utf-8") if isinstance(result.stderr, bytes) else result.stderr

        if stderr_str:
            print("Lambda Logs:")
            print(stderr_str)
        if stdout_str:
            print("Command Output:")
            print(stdout_str)

        return stdout_str, stderr_str, result.process.returncode

    def start_command_with_streaming(self, command_list, test_name, env=None, cwd=None):
        """Start a command and stream output in real-time.

        Returns:
            tuple: (process, output_lines, thread) where output_lines is a list that gets populated as output arrives
        """
        process = Popen(command_list, stdout=PIPE, stderr=STDOUT, stdin=PIPE, text=True, env=env, cwd=cwd)
        output_lines = []

        def log_output():
            for line in iter(process.stdout.readline, ""):
                output_lines.append(line)

        thread = threading.Thread(target=log_output, daemon=True)
        thread.start()

        return process, output_lines, thread

    def assert_invoke_output(
        self,
        stdout: str,
        input_data: Dict[str, Any] = {},
        execution_name: Optional[str] = None,
        expected_status: str = "SUCCEEDED",
    ) -> str:
        """Assert invoke output contains expected fields and return execution ARN."""
        stdout_str = stdout.strip()

        self.assertIn("Execution Summary:", stdout_str, f"Expected execution summary in output: {stdout_str}")

        arn_match = re.search(r"ARN:\s+([a-f0-9-]+)", stdout_str)
        self.assertIsNotNone(arn_match, f"Could not find ARN in output: {stdout_str}")
        execution_arn = arn_match.group(1) if arn_match else ""

        if execution_name:
            self.assertIn(
                f"Name:     {execution_name}",
                stdout_str,
                f"Expected execution name '{execution_name}' in output: {stdout_str}",
            )

        self.assertIn(
            f"Status:   {expected_status}", stdout_str, f"Expected status '{expected_status}' in output: {stdout_str}"
        )

        expected_input_json = json.dumps(input_data, indent=2)
        self.assertIn(f"Input:    {expected_input_json}", stdout_str, f"Expected input JSON in output: {stdout_str}")

        return execution_arn

    def assert_execution_history(self, history: dict, example):
        """Assert execution history matches expected history from file."""
        self.assertIn("Events", history)
        actual_events = history["Events"]

        expected_history_path = Path(self.test_data_path, "durable", example.expected_history_file)
        with open(expected_history_path) as f:
            expected_events = json.load(f)

        self.assertEqual(len(actual_events), len(expected_events), "Event count mismatch")

        for i, (actual, expected) in enumerate(zip(actual_events, expected_events)):
            with self.subTest(event_index=i):
                self.assertEqual(actual["EventId"], expected["EventId"], f"EventId {i} mismatch")
                self.assertEqual(actual["EventType"], expected["EventType"], f"EventType {i} mismatch")
                self.assertEqual(actual.get("SubType"), expected.get("SubType"), f"SubType {i} mismatch")

                if not example.skip_payload_assertions:
                    self.assertEqual(actual.get("Name"), expected.get("Name"), f"Name {i} mismatch")

                    detail_fields = [
                        "ExecutionStartedDetails",
                        "ExecutionSucceededDetails",
                        "ExecutionFailedDetails",
                        "StepStartedDetails",
                        "StepSucceededDetails",
                        "StepFailedDetails",
                    ]
                    for field in detail_fields:
                        self.assertEqual(actual.get(field), expected.get(field), f"{field} {i} mismatch")
