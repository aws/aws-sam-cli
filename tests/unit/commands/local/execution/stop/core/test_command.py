"""
Unit tests for execution stop core command
"""

import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.execution.stop.core.command import LocalExecutionStopCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalExecutionStopCommand(TestCase):
    """Test cases for LocalExecutionStopCommand"""

    @patch.object(LocalExecutionStopCommand, "get_params")
    def test_format_options(self, mock_get_params):
        """Test format_options method"""
        # Arrange
        ctx = Mock()
        ctx.command_path = "sam local execution stop"
        formatter = MockFormatter(scrub_text=True)

        mock_get_params.return_value = [
            MockParams(rv=("durable_execution_arn", "Durable execution ARN"), name="durable_execution_arn"),
            MockParams(rv=("--error-message", "Error message"), name="error_message"),
            MockParams(rv=("--error-type", "Error type"), name="error_type"),
            MockParams(rv=("--error-data", "Error data"), name="error_data"),
            MockParams(rv=("--stack-trace", "Stack trace entries"), name="stack_trace"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--help", ""), name="help"),
        ]

        command = LocalExecutionStopCommand(name="stop", description="Stop a durable function execution")
        expected_output = {
            "Description": [
                (
                    "Stop a durable function execution\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m",
                    "",
                )
            ],
            "Examples": [],
            "Stop execution without error details": [
                (
                    "$ sam local execution stop c63eec67-3415-4eb4-a495-116aa3a86278\x1b[0m",
                    "",
                ),
            ],
            "Stop execution with error message and type": [
                (
                    '$ sam local execution stop c63eec67-3415-4eb4-a495-116aa3a86278 --error-message "Execution cancelled" --error-type "UserCancellation"\x1b[0m',
                    "",
                ),
            ],
            "Stop execution with full error details and stack trace": [
                (
                    '$ sam local execution stop c63eec67-3415-4eb4-a495-116aa3a86278 --error-message "Task failed" --error-type "TaskFailure" --error-data \'{"reason":"timeout"}\' --stack-trace "at function1()" --stack-trace "at function2()"\x1b[0m',
                    "",
                ),
            ],
            "Stop Options": [
                ("", ""),
                ("--error-message", ""),
                ("", ""),
                ("--error-type", ""),
                ("", ""),
                ("--error-data", ""),
                ("", ""),
                ("--stack-trace", ""),
                ("", ""),
            ],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", ""), ("--help", ""), ("", "")],
        }

        # Act
        command.format_options(ctx, formatter)

        # Assert
        self.assertEqual(formatter.data, expected_output)
