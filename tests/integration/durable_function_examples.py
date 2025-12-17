"""
Enum definitions for durable function test examples.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional


class DurableFunctionExamples(Enum):
    """Enum for durable function test examples."""

    HELLO_WORLD = ("HelloWorld", "hello_world", False, "expected_history.json", False)
    NAMED_STEP = ("NamedStep", "step", False, "expected_history.json", False)
    NAMED_WAIT = ("NamedWait", "wait", False, "expected_history.json", False)
    MAP_OPERATIONS = ("MapOperations", "map", True, "expected_history.json", False)
    PARALLEL = ("Parallel", "parallel", True, "expected_history.json", True)
    EXECUTION_TIMEOUT = ("ExecutionTimeout", "timeout", True, "expected_history.json", False)
    WAIT_FOR_CALLBACK = ("WaitForCallback", "wait_for_callback", True, "expected_history.json", False)
    WAIT_FOR_CALLBACK_FAILURE = ("WaitForCallback", "wait_for_callback", True, "expected_history_failure.json", False)

    def __init__(
        self,
        function_name: str,
        directory: str,
        skip_payload_assertions: bool,
        history_file: str,
        skip_history_assertions: bool,
    ):
        self._function_name = function_name
        self._directory = directory
        self._skip_payload_assertions = skip_payload_assertions
        self._history_file = history_file
        self._skip_history_assertions = skip_history_assertions

    @property
    def function_name(self) -> str:
        """Get the function name for this example."""
        return self._function_name

    @property
    def expected_history_file(self) -> str:
        """Get the expected history filename for this example."""
        return f"functions/{self._directory}/{self._history_file}"

    @property
    def skip_payload_assertions(self) -> bool:
        """Whether to skip payload assertions for non-deterministic tests."""
        return self._skip_payload_assertions

    @property
    def skip_history_assertions(self) -> bool:
        """Whether to skip history assertions for tests with non-deterministic event ordering."""
        return self._skip_history_assertions

    def get_expected_response(self, test_data_path: Path) -> Optional[str]:
        """Extract expected response from ExecutionSucceededDetails in history file."""
        history_file = test_data_path / "durable" / self.expected_history_file
        with open(history_file) as f:
            history = json.load(f)

        for event in history:
            if event.get("EventType") == "ExecutionSucceeded":
                result = event.get("ExecutionSucceededDetails", {}).get("Result", {})
                payload = result.get("Payload")
                if payload is not None:
                    return str(payload)

        return None
