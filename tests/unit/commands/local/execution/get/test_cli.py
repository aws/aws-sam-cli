"""
Unit tests for sam local execution get CLI command
"""

import json
import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.local.execution.get.cli import cli, do_cli, _get_durable_execution


class TestLocalExecutionGetCliCommand(TestCase):
    """Test cases for CLI command functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

    @patch("samcli.commands.local.execution.get.cli._get_durable_execution")
    @patch("samcli.commands.local.execution.get.cli.format_execution_details")
    @patch("click.echo")
    def test_do_cli_success_summary(self, mock_echo, mock_format_execution_details, mock_get_execution):
        """Test successful execution with summary format"""
        expected_response = {
            "DurableExecutionArn": self.test_execution_id,
            "Status": "Running",
            "StartTime": "2023-01-01T00:00:00Z",
            "Input": '{"test": "input"}',
        }
        mock_get_execution.return_value = expected_response
        mock_format_execution_details.return_value = "formatted summary"

        do_cli(self.test_execution_id, "summary")

        mock_get_execution.assert_called_once_with(durable_execution_arn=self.test_execution_id)
        mock_format_execution_details.assert_called_once_with(self.test_execution_id, expected_response, "summary")
        mock_echo.assert_called_once_with("formatted summary")

    @patch("samcli.commands.local.execution.get.cli._get_durable_execution")
    @patch("click.echo")
    def test_do_cli_success_json(self, mock_echo, mock_get_execution):
        """Test successful execution with JSON format"""
        # Arrange
        expected_response = {
            "DurableExecutionArn": self.test_execution_id,
            "Status": "Running",
            "StartTime": "2023-01-01T00:00:00Z",
            "Input": '{"test": "input"}',
        }
        mock_get_execution.return_value = expected_response

        do_cli(self.test_execution_id, "json")

        mock_get_execution.assert_called_once_with(durable_execution_arn=self.test_execution_id)
        mock_echo.assert_called_once()
        echoed_output = mock_echo.call_args[0][0]
        self.assertEqual(json.loads(echoed_output), expected_response)

    @patch("samcli.commands.local.execution.get.cli._get_durable_execution")
    def test_do_cli_client_error(self, mock_get_execution):
        """Test error handling when client fails"""
        # Arrange
        mock_get_execution.side_effect = Exception("Connection failed")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            do_cli(self.test_execution_id, "summary")

        self.assertEqual(str(context.exception), "Connection failed")

    def test_cli_no_arguments_raises_error(self):
        """Test CLI command with no arguments raises error"""
        # Act & Assert
        result = self.runner.invoke(cli, [])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)

    @patch("samcli.commands.local.execution.get.cli.do_cli")
    def test_cli_with_positional_argument(self, mock_do_cli):
        """Test CLI command with positional argument"""
        # Act
        result = self.runner.invoke(cli, [self.test_execution_id])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_do_cli.assert_called_once_with(self.test_execution_id, "summary")


class TestLocalGetDurableExecutionFunction(TestCase):
    """Test cases for _get_durable_execution function"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

    @patch("samcli.commands.local.execution.get.cli.DurableContext")
    def test_get_durable_execution_success(self, mock_context_class):
        """Test successful get_durable_execution call"""
        # Arrange
        mock_client = Mock()
        expected_response = {
            "DurableExecutionArn": self.test_execution_id,
            "Status": "Running",
            "StartTime": "2023-01-01T00:00:00Z",
            "Input": '{"test": "input"}',
        }
        mock_client.get_durable_execution.return_value = expected_response

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        result = _get_durable_execution(self.test_execution_id)

        # Assert
        mock_context_class.assert_called_once()
        mock_client.get_durable_execution.assert_called_once_with(self.test_execution_id)
        self.assertEqual(result, expected_response)

    @patch("samcli.commands.local.execution.get.cli.DurableContext")
    def test_get_durable_execution_client_creation_error(self, mock_context_class):
        """Test error handling when client creation fails"""
        # Arrange
        mock_context_class.return_value.__enter__.side_effect = Exception("Context creation failed")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            _get_durable_execution(self.test_execution_id)

        self.assertEqual(str(context.exception), "Context creation failed")

    @patch("samcli.commands.local.execution.get.cli.DurableContext")
    def test_get_durable_execution_uses_emulator_port(self, mock_context_class):
        """Test that the function uses DurableContext correctly"""
        # Arrange
        mock_client = Mock()
        mock_client.get_durable_execution.return_value = {"Status": "Running"}

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        _get_durable_execution(self.test_execution_id)

        # Assert
        mock_context_class.assert_called_once()
