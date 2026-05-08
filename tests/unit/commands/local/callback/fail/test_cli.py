"""
Unit tests for sam local callback fail CLI command
"""

import json
import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.local.callback.fail.cli import cli, do_cli, _send_callback_failure


class TestFailCommand(TestCase):
    """Test cases for callback fail command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_callback_id = "test-callback-123"

    @patch("samcli.commands.local.callback.fail.cli._send_callback_failure")
    @patch("samcli.commands.local.callback.fail.cli.format_callback_failure_message")
    @patch("click.echo")
    def test_do_cli_success(self, mock_echo, mock_get_message, mock_send_callback):
        """Test successful execution of do_cli"""
        # Arrange
        expected_message = "❌ Callback failure sent for ID: test-callback-123"
        mock_get_message.return_value = expected_message

        # Act
        do_cli(self.test_callback_id, None, (), None, None)

        # Assert
        mock_send_callback.assert_called_once_with(
            callback_id=self.test_callback_id,
            error_data=None,
            stack_trace=None,
            error_type=None,
            error_message=None,
        )
        mock_get_message.assert_called_once_with(self.test_callback_id, None, None, None)
        mock_echo.assert_called_once_with(expected_message)

    @patch("samcli.commands.local.callback.fail.cli._send_callback_failure")
    @patch("samcli.commands.local.callback.fail.cli.format_callback_failure_message")
    @patch("click.echo")
    def test_do_cli_with_non_json_serializable_objects(self, mock_echo, mock_get_message, mock_send_callback):
        """Test do_cli handles failure message formatting"""
        # Arrange
        expected_message = "❌ Callback failure sent for ID: test-callback-123"
        mock_get_message.return_value = expected_message

        # Act
        do_cli(self.test_callback_id, None, (), None, None)

        # Assert
        mock_send_callback.assert_called_once_with(
            callback_id=self.test_callback_id,
            error_data=None,
            stack_trace=None,
            error_type=None,
            error_message=None,
        )
        mock_get_message.assert_called_once_with(self.test_callback_id, None, None, None)
        mock_echo.assert_called_once_with(expected_message)

    @patch("samcli.commands.local.callback.fail.cli._send_callback_failure")
    def test_do_cli_failure(self, mock_send_callback):
        """Test failure handling in do_cli"""
        # Arrange
        mock_send_callback.side_effect = Exception("Test error")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            do_cli(self.test_callback_id, None, (), None, None)

        self.assertEqual(str(context.exception), "Test error")

    @patch("samcli.commands.local.callback.fail.cli.DurableContext")
    def test_send_callback_failure(self, mock_context_class):
        """Test successful callback failure sending"""
        # Arrange
        expected_result = {}
        mock_client = Mock()
        mock_client.send_callback_failure.return_value = expected_result

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        result = _send_callback_failure(
            self.test_callback_id,
            "error data",
            "stack trace",
            "TypeError",
            "detailed message",
        )

        # Assert
        self.assertEqual(result, expected_result)
        mock_context_class.assert_called_once()
        mock_client.send_callback_failure.assert_called_once_with(
            self.test_callback_id,
            "error data",
            "stack trace",
            "TypeError",
            "detailed message",
        )

    @patch("samcli.commands.local.callback.fail.cli.DurableContext")
    def test_send_callback_failure_exception(self, mock_context_class):
        """Test exception handling in _send_callback_failure"""
        # Arrange
        mock_client = Mock()
        mock_client.send_callback_failure.side_effect = Exception("Client error")

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act & Assert
        with self.assertRaises(UserException) as context:
            _send_callback_failure(self.test_callback_id, None, None, None, None)

        self.assertEqual(str(context.exception), "Client error")

    @patch("samcli.commands.local.callback.fail.cli.format_callback_failure_message")
    @patch("click.echo")
    @patch("samcli.commands.local.callback.fail.cli._send_callback_failure")
    def test_do_cli_with_all_parameters(self, mock_send_callback, mock_echo, mock_get_message):
        """Test do_cli with all new error parameters"""
        # Arrange
        expected_message = "❌ Callback failure sent for ID: test-callback-123\nError Type: TypeError\nError Message: detailed error message\nError Data: additional data"
        mock_get_message.return_value = expected_message

        # Act
        do_cli(
            self.test_callback_id,
            "additional data",
            ("stack trace line 1", "stack trace line 2"),
            "TypeError",
            "detailed error message",
        )

        # Assert
        mock_send_callback.assert_called_once_with(
            callback_id=self.test_callback_id,
            error_data="additional data",
            stack_trace=["stack trace line 1", "stack trace line 2"],
            error_type="TypeError",
            error_message="detailed error message",
        )
        mock_get_message.assert_called_once_with(
            self.test_callback_id, "additional data", "TypeError", "detailed error message"
        )
        mock_echo.assert_called_once_with(expected_message)
