"""
Unit tests for callback fail core command
"""

import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.callback.fail.core.command import LocalCallbackFailCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestCallbackFailCommand(TestCase):
    """Test cases for CallbackFailCommand"""

    @patch.object(LocalCallbackFailCommand, "get_params")
    def test_format_options(self, mock_get_params):
        """Test format_options method"""
        # Arrange
        ctx = Mock()
        ctx.command_path = "sam local callback fail"
        formatter = MockFormatter(scrub_text=True)

        mock_get_params.return_value = [
            MockParams(rv=("callback_id", "Callback ID"), name="callback_id"),
            MockParams(rv=("--error-data", "Additional error data"), name="error_data"),
            MockParams(rv=("--stack-trace", "Stack trace information"), name="stack_trace"),
            MockParams(rv=("--error-type", "Type of error"), name="error_type"),
            MockParams(rv=("--error-message", "Detailed error message"), name="error_message"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        command = LocalCallbackFailCommand(name="fail", description="Send failure callback")
        expected_output = {
            "Description": [
                ("Send failure callback\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "Send failure callback with no parameters": [
                ("", ""),
                ("$ sam local callback fail my-callback-id\x1b[0m", ""),
            ],
            "Send failure callback with error message": [
                ("", ""),
                ("$ sam local callback fail my-callback-id --error-message 'Task failed'\x1b[0m", ""),
            ],
            "Send failure callback with additional error details": [
                ("", ""),
                (
                    "$ sam local callback fail my-callback-id --error-message 'Task failed' --error-type 'ValidationError' --stack-trace 'at line 42' --error-data '{\"code\": 500}'\x1b[0m",
                    "",
                ),
            ],
            "Callback Options": [
                ("", ""),
                ("--error-data", ""),
                ("", ""),
                ("--stack-trace", ""),
                ("", ""),
                ("--error-type", ""),
                ("", ""),
                ("--error-message", ""),
                ("", ""),
            ],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        # Act
        command.format_options(ctx, formatter)

        # Assert
        self.assertEqual(formatter.data, expected_output)
