"""
Unit tests for sam local callback heartbeat CLI command
"""

import json
import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.local.callback.heartbeat.cli import cli, do_cli, _send_callback_heartbeat


class TestHeartbeatCommand(TestCase):
    """Test cases for callback heartbeat command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_callback_id = "test-callback-123"

    @patch("samcli.commands.local.callback.heartbeat.cli._send_callback_heartbeat")
    @patch("samcli.commands.local.callback.heartbeat.cli.format_callback_heartbeat_message")
    @patch("click.echo")
    def test_do_cli_success(self, mock_echo, mock_get_message, mock_send_callback):
        """Test successful execution of do_cli"""
        # Arrange
        expected_message = "💓 Callback heartbeat sent for ID: test-callback-123"
        mock_get_message.return_value = expected_message

        # Act
        do_cli(self.test_callback_id)

        # Assert
        mock_send_callback.assert_called_once_with(callback_id=self.test_callback_id)
        mock_get_message.assert_called_once_with(self.test_callback_id)
        mock_echo.assert_called_once_with(expected_message)

    @patch("samcli.commands.local.callback.heartbeat.cli._send_callback_heartbeat")
    @patch("samcli.commands.local.callback.heartbeat.cli.format_callback_heartbeat_message")
    @patch("click.echo")
    def test_do_cli_with_non_json_serializable_objects(self, mock_echo, mock_get_message, mock_send_callback):
        """Test do_cli handles heartbeat message formatting"""
        # Arrange
        expected_message = "💓 Callback heartbeat sent for ID: test-callback-123"
        mock_get_message.return_value = expected_message

        # Act
        do_cli(self.test_callback_id)

        # Assert
        mock_send_callback.assert_called_once_with(callback_id=self.test_callback_id)
        mock_get_message.assert_called_once_with(self.test_callback_id)
        mock_echo.assert_called_once_with(expected_message)

    @patch("samcli.commands.local.callback.heartbeat.cli._send_callback_heartbeat")
    def test_do_cli_failure(self, mock_send_callback):
        """Test failure handling in do_cli"""
        # Arrange
        mock_send_callback.side_effect = Exception("Test error")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            do_cli(self.test_callback_id)

        self.assertEqual(str(context.exception), "Test error")

    @patch("samcli.commands.local.callback.heartbeat.cli.DurableContext")
    def test_send_callback_heartbeat(self, mock_context_class):
        """Test successful callback heartbeat sending"""
        # Arrange
        expected_result = {}
        mock_client = Mock()
        mock_client.send_callback_heartbeat.return_value = expected_result

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        result = _send_callback_heartbeat(self.test_callback_id)

        # Assert
        self.assertEqual(result, expected_result)
        mock_context_class.assert_called_once()
        mock_client.send_callback_heartbeat.assert_called_once_with(self.test_callback_id)

    @patch("samcli.commands.local.callback.heartbeat.cli.DurableContext")
    def test_send_callback_heartbeat_exception(self, mock_context_class):
        """Test exception handling in _send_callback_heartbeat"""
        # Arrange
        mock_client = Mock()
        mock_client.send_callback_heartbeat.side_effect = Exception("Client error")

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act & Assert
        with self.assertRaises(UserException) as context:
            _send_callback_heartbeat(self.test_callback_id)

        self.assertEqual(str(context.exception), "Client error")
