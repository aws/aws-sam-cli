"""
Unit tests for callback heartbeat core command
"""

import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.callback.heartbeat.core.command import LocalCallbackHeartbeatCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestCallbackHeartbeatCommand(TestCase):
    """Test cases for CallbackHeartbeatCommand"""

    @patch.object(LocalCallbackHeartbeatCommand, "get_params")
    def test_format_options(self, mock_get_params):
        """Test format_options method"""
        # Arrange
        ctx = Mock()
        ctx.command_path = "sam local callback heartbeat"
        formatter = MockFormatter(scrub_text=True)

        mock_get_params.return_value = [
            MockParams(rv=("callback_id", "Callback ID"), name="callback_id"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        command = LocalCallbackHeartbeatCommand(name="heartbeat", description="Send heartbeat callback")
        expected_output = {
            "Description": [
                ("Send heartbeat callback\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "Send heartbeat callback": [("", ""), ("$ sam local callback heartbeat my-callback-id\x1b[0m", "")],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }

        # Act
        command.format_options(ctx, formatter)

        # Assert
        self.assertEqual(formatter.data, expected_output)
