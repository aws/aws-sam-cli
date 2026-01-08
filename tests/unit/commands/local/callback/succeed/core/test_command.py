"""
Unit tests for callback succeed core command
"""

import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.callback.succeed.core.command import LocalCallbackSucceedCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalCallbackSucceedCommand(TestCase):
    """Test cases for LocalCallbackSucceedCommand"""

    @patch.object(LocalCallbackSucceedCommand, "get_params")
    def test_format_options(self, mock_get_params):
        """Test format_options method"""
        # Arrange
        ctx = Mock()
        ctx.command_path = "sam local callback succeed"
        formatter = MockFormatter(scrub_text=True)

        mock_get_params.return_value = [
            MockParams(rv=("callback_id", "Callback ID"), name="callback_id"),
            MockParams(rv=("--result", "Result data"), name="result"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        command = LocalCallbackSucceedCommand(name="succeed", description="Send success callback")
        expected_output = {
            "Description": [
                ("Send success callback\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "Send success callback with no result": [
                ("", ""),
                ("$ sam local callback succeed my-callback-id\x1b[0m", ""),
            ],
            "Send success callback with result": [
                ("", ""),
                ("$ sam local callback succeed my-callback-id --result 'Task completed successfully'\x1b[0m", ""),
            ],
            "Send success callback with short option": [
                ("", ""),
                ("$ sam local callback succeed my-callback-id -r 'Success result'\x1b[0m", ""),
            ],
            "Callback Options": [("", ""), ("--result", ""), ("", "")],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        # Act
        command.format_options(ctx, formatter)

        # Assert
        self.assertEqual(formatter.data, expected_output)
