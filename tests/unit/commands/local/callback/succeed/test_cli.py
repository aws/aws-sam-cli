"""
Unit tests for sam local callback succeed CLI command
"""

import json
import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.exceptions import UserException
from samcli.commands.local.callback.succeed.cli import cli, do_cli, _send_callback_success


class TestSucceedCommand(TestCase):
    """Test cases for callback succeed command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_callback_id = "test-callback-123"

    @patch("samcli.commands.local.callback.succeed.cli._send_callback_success")
    @patch("samcli.commands.local.callback.succeed.cli.format_callback_success_message")
    @patch("click.echo")
    def test_do_cli_success(self, mock_echo, mock_get_message, mock_send_callback):
        """Test successful execution of do_cli"""
        # Arrange
        expected_message = "✅ Callback success sent for ID: test-callback-123\nResult: test result"
        mock_get_message.return_value = expected_message

        # Act
        do_cli(self.test_callback_id, "test result")

        # Assert
        mock_send_callback.assert_called_once_with(callback_id=self.test_callback_id, result="test result")
        mock_get_message.assert_called_once_with(self.test_callback_id, "test result")
        mock_echo.assert_called_once_with(expected_message)

    @patch("samcli.commands.local.callback.succeed.cli._send_callback_success")
    @patch("samcli.commands.local.callback.succeed.cli.format_callback_success_message")
    @patch("click.echo")
    def test_do_cli_with_non_json_serializable_objects(self, mock_echo, mock_get_message, mock_send_callback):
        """Test do_cli handles success message formatting"""
        # Arrange
        expected_message = "✅ Callback success sent for ID: test-callback-123"
        mock_get_message.return_value = expected_message

        # Act
        do_cli(self.test_callback_id, None)

        # Assert
        mock_send_callback.assert_called_once_with(callback_id=self.test_callback_id, result=None)
        mock_get_message.assert_called_once_with(self.test_callback_id, None)
        mock_echo.assert_called_once_with(expected_message)

    @patch("samcli.commands.local.callback.succeed.cli._send_callback_success")
    def test_do_cli_failure(self, mock_send_callback):
        """Test failure handling in do_cli"""
        # Arrange
        mock_send_callback.side_effect = Exception("Test error")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            do_cli(self.test_callback_id, None)

        self.assertEqual(str(context.exception), "Test error")

    @patch("samcli.commands.local.callback.succeed.cli.DurableContext")
    def test_send_callback_success(self, mock_context_class):
        """Test successful callback sending"""
        # Arrange
        expected_result = {}
        mock_client = Mock()
        mock_client.send_callback_success.return_value = expected_result

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        result = _send_callback_success(self.test_callback_id, "test result")

        # Assert
        self.assertEqual(result, expected_result)
        mock_context_class.assert_called_once()
        mock_client.send_callback_success.assert_called_once_with(self.test_callback_id, "test result")

    @patch("samcli.commands.local.callback.succeed.cli.DurableContext")
    def test_send_callback_success_exception(self, mock_context_class):
        """Test exception handling in _send_callback_success"""
        # Arrange
        mock_client = Mock()
        mock_client.send_callback_success.side_effect = Exception("Client error")

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act & Assert
        with self.assertRaises(UserException) as context:
            _send_callback_success(self.test_callback_id, "test result")

        self.assertEqual(str(context.exception), "Client error")
