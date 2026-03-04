"""
Unit tests for sam local execution history CLI command
"""

import json
import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.local.execution.history.cli import cli, do_cli, _get_durable_execution_history


class TestLocalExecutionHistoryCliCommand(TestCase):
    """Test cases for CLI command functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

    @patch("samcli.commands.local.execution.history.cli._get_durable_execution_history")
    @patch("click.echo")
    def test_do_cli_success_default_table_format(self, mock_echo, mock_get_execution_history):
        """Test successful execution of do_cli with default table format"""
        # Arrange
        expected_result = {
            "Events": [
                {"EventType": "ExecutionStarted", "EventId": 1, "EventTimestamp": "2023-01-01T00:00:00Z"},
            ],
        }
        mock_get_execution_history.return_value = expected_result

        # Act
        do_cli(self.test_execution_id, "table")

        # Assert
        mock_get_execution_history.assert_called_once_with(durable_execution_arn=self.test_execution_id)
        # Should output table format by default (contains table characters)
        call_args = mock_echo.call_args[0][0]
        self.assertIn("│", call_args)
        self.assertIn("┌", call_args)

    @patch("samcli.commands.local.execution.history.cli._get_durable_execution_history")
    @patch("click.echo")
    def test_do_cli_success_json_format(self, mock_echo, mock_get_execution_history):
        """Test successful execution of do_cli with JSON format"""
        # Arrange
        expected_result = {
            "Events": [
                {"EventType": "ExecutionStarted", "EventId": 1, "EventTimestamp": "2023-01-01T00:00:00Z"},
            ],
        }
        mock_get_execution_history.return_value = expected_result

        # Act
        do_cli(self.test_execution_id, "json")

        # Assert
        mock_get_execution_history.assert_called_once_with(durable_execution_arn=self.test_execution_id)
        mock_echo.assert_called_once_with(json.dumps(expected_result, indent=2, default=str))

    @patch("samcli.commands.local.execution.history.cli._get_durable_execution_history")
    @patch("click.echo")
    def test_do_cli_with_non_json_serializable_objects(self, mock_echo, mock_get_execution_history):
        """Test do_cli handles non-JSON-serializable objects using default=str"""
        # Arrange
        mock_get_execution_history.return_value = {"foo": object()}

        # Act
        do_cli(self.test_execution_id, "table")

        # Assert
        mock_get_execution_history.assert_called_once_with(durable_execution_arn=self.test_execution_id)
        mock_echo.assert_called_once()

    @patch("samcli.commands.local.execution.history.cli._get_durable_execution_history")
    def test_do_cli_failure(self, mock_get_execution_history):
        """Test failure handling in do_cli"""
        # Arrange
        mock_get_execution_history.side_effect = Exception("Test error")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            do_cli(self.test_execution_id, "table")

        mock_get_execution_history.assert_called_once_with(durable_execution_arn=self.test_execution_id)
        self.assertEqual(str(context.exception), "Test error")

    def test_cli_command_with_valid_arn(self):
        """Test CLI command with valid ARN"""
        with patch("samcli.commands.local.execution.history.cli.do_cli") as mock_do_cli:
            result = self.runner.invoke(cli, [self.test_execution_id])

            self.assertEqual(result.exit_code, 0)
            mock_do_cli.assert_called_once_with(self.test_execution_id, "table")  # default format

    def test_cli_command_with_json_format(self):
        """Test CLI command with JSON format"""
        with patch("samcli.commands.local.execution.history.cli.do_cli") as mock_do_cli:
            result = self.runner.invoke(cli, [self.test_execution_id, "--format", "json"])

            self.assertEqual(result.exit_code, 0)
            mock_do_cli.assert_called_once_with(self.test_execution_id, "json")

    def test_cli_command_missing_arn(self):
        """Test CLI command without required ARN argument"""
        result = self.runner.invoke(cli, [])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)


class TestLocalGetDurableExecutionHistoryFunction(TestCase):
    """Test cases for _get_durable_execution_history function"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

    @patch("samcli.commands.local.execution.history.cli.DurableContext")
    def test_get_durable_execution_history_success(self, mock_context_class):
        """Test successful retrieval of execution history"""
        # Arrange
        expected_result = {
            "Events": [{"EventType": "ExecutionStarted", "EventId": 1, "EventTimestamp": "2023-01-01T00:00:00Z"}],
        }

        mock_client = Mock()
        mock_client.get_durable_execution_history.return_value = expected_result

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        result = _get_durable_execution_history(self.test_execution_id)

        # Assert
        self.assertEqual(result, expected_result)
        mock_context_class.assert_called_once()
        mock_client.get_durable_execution_history.assert_called_once_with(self.test_execution_id)

    @patch("samcli.commands.local.execution.history.cli.DurableContext")
    def test_get_durable_execution_history_failure(self, mock_context_class):
        """Test failure handling in _get_durable_execution_history"""
        # Arrange
        mock_client = Mock()
        mock_client.get_durable_execution_history.side_effect = Exception("Connection error")

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act & Assert
        with self.assertRaises(UserException) as context:
            _get_durable_execution_history(self.test_execution_id)

        mock_client.get_durable_execution_history.assert_called_once_with(self.test_execution_id)
        self.assertEqual(str(context.exception), "Connection error")
