"""
Unit tests for sam local execution stop CLI command
"""

import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.local.execution.stop.cli import cli, do_cli, _stop_durable_execution


class TestLocalExecutionStopCliCommand(TestCase):
    """Test cases for CLI command functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

    @patch("samcli.commands.local.execution.stop.cli._stop_durable_execution")
    @patch("samcli.commands.local.execution.stop.cli.format_stop_execution_message")
    @patch("click.echo")
    def test_do_cli_success(self, mock_echo, mock_format, mock_stop_execution):
        """Test successful execution of do_cli"""
        # Arrange
        mock_format.return_value = "🛑 Execution stopped: c63eec67-3415-4eb4-a495-116aa3a86278"

        # Act
        do_cli(self.test_execution_id)

        # Assert
        mock_stop_execution.assert_called_once_with(
            durable_execution_arn=self.test_execution_id,
            error_message=None,
            error_type=None,
            error_data=None,
            stack_trace=None,
        )
        mock_format.assert_called_once_with(self.test_execution_id, None, None, None)
        mock_echo.assert_called_once_with("🛑 Execution stopped: c63eec67-3415-4eb4-a495-116aa3a86278")

    @patch("samcli.commands.local.execution.stop.cli._stop_durable_execution")
    @patch("samcli.commands.local.execution.stop.cli.format_stop_execution_message")
    @patch("click.echo")
    def test_do_cli_success_with_error_params(self, mock_echo, mock_format, mock_stop_execution):
        """Test successful execution of do_cli with error parameters"""
        # Arrange
        test_error_message = "Test error message"
        test_error_type = "TEST_ERROR"
        test_error_data = "Additional error data"
        test_stack_trace = ["line1", "line2"]
        mock_format.return_value = "🛑 Execution stopped: c63eec67-3415-4eb4-a495-116aa3a86278\nError Type: TEST_ERROR\nError Message: Test error message\nError Data: Additional error data"

        # Act
        do_cli(
            self.test_execution_id,
            error_message=test_error_message,
            error_type=test_error_type,
            error_data=test_error_data,
            stack_trace=test_stack_trace,
        )

        # Assert
        mock_stop_execution.assert_called_once_with(
            durable_execution_arn=self.test_execution_id,
            error_message=test_error_message,
            error_type=test_error_type,
            error_data=test_error_data,
            stack_trace=test_stack_trace,
        )
        mock_format.assert_called_once_with(
            self.test_execution_id, test_error_type, test_error_message, test_error_data
        )
        mock_echo.assert_called_once()

    @patch("samcli.commands.local.execution.stop.cli._stop_durable_execution")
    def test_do_cli_client_error(self, mock_stop_execution):
        """Test error handling when client fails"""
        # Arrange
        mock_stop_execution.side_effect = Exception("Client error")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            do_cli(self.test_execution_id)
        self.assertEqual(str(context.exception), "Client error")

    @patch("samcli.commands.local.execution.stop.cli.do_cli")
    def test_cli_command_with_valid_arn(self, mock_do_cli):
        """Test CLI command with valid ARN"""
        # Act
        result = self.runner.invoke(cli, [self.test_execution_id])

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_do_cli.assert_called_once_with(self.test_execution_id, None, None, None, [])

    @patch("samcli.commands.local.execution.stop.cli.do_cli")
    def test_cli_command_with_error_options(self, mock_do_cli):
        """Test CLI command with error options"""
        # Act
        result = self.runner.invoke(
            cli,
            [
                self.test_execution_id,
                "--error-message",
                "Test error",
                "--error-type",
                "TEST_TYPE",
                "--error-data",
                "Test data",
                "--stack-trace",
                "line1",
                "--stack-trace",
                "line2",
            ],
        )

        # Assert
        self.assertEqual(result.exit_code, 0)
        mock_do_cli.assert_called_once_with(
            self.test_execution_id, "Test error", "TEST_TYPE", "Test data", ["line1", "line2"]
        )

    def test_cli_command_missing_arn(self):
        """Test CLI command without required ARN argument"""
        # Act
        result = self.runner.invoke(cli, [])

        # Assert
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)


class TestLocalStopDurableExecutionFunction(TestCase):
    """Test cases for _stop_durable_execution function"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

    @patch("samcli.commands.local.execution.stop.cli.DurableContext")
    def test_stop_durable_execution_success(self, mock_context_class):
        """Test successful stop_durable_execution call"""
        # Arrange
        mock_client = Mock()
        expected_response = {"StopDate": "2023-01-01T00:00:00Z"}
        mock_client.stop_durable_execution.return_value = expected_response

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        result = _stop_durable_execution(self.test_execution_id)

        # Assert
        mock_context_class.assert_called_once()
        mock_client.stop_durable_execution.assert_called_once_with(
            self.test_execution_id,
            error_message=None,
            error_type=None,
            error_data=None,
            stack_trace=None,
        )
        self.assertEqual(result, expected_response)

    @patch("samcli.commands.local.execution.stop.cli.DurableContext")
    def test_stop_durable_execution_success_with_error_params(self, mock_context_class):
        """Test successful stop_durable_execution call with error parameters"""
        # Arrange
        mock_client = Mock()
        expected_response = {"StopDate": "2023-01-01T00:00:00Z"}
        mock_client.stop_durable_execution.return_value = expected_response
        test_error_message = "Test error message"
        test_error_type = "TEST_ERROR"
        test_error_data = "Additional error data"
        test_stack_trace = ["line1", "line2"]

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act
        result = _stop_durable_execution(
            self.test_execution_id,
            error_message=test_error_message,
            error_type=test_error_type,
            error_data=test_error_data,
            stack_trace=test_stack_trace,
        )

        # Assert
        mock_context_class.assert_called_once()
        mock_client.stop_durable_execution.assert_called_once_with(
            self.test_execution_id,
            error_message=test_error_message,
            error_type=test_error_type,
            error_data=test_error_data,
            stack_trace=test_stack_trace,
        )
        self.assertEqual(result, expected_response)

    @patch("samcli.commands.local.execution.stop.cli.DurableContext")
    def test_stop_durable_execution_client_creation_error(self, mock_context_class):
        """Test error handling when client creation fails"""
        # Arrange
        mock_context_class.return_value.__enter__.side_effect = Exception("Client creation failed")

        # Act & Assert
        with self.assertRaises(UserException) as context:
            _stop_durable_execution(self.test_execution_id)
        self.assertEqual(str(context.exception), "Client creation failed")

    @patch("samcli.commands.local.execution.stop.cli.DurableContext")
    def test_stop_durable_execution_client_error(self, mock_context_class):
        """Test error handling when client call fails"""
        # Arrange
        mock_client = Mock()
        mock_client.stop_durable_execution.side_effect = Exception("Lambda client error")

        mock_context = Mock()
        mock_context.client = mock_client
        mock_context_class.return_value.__enter__.return_value = mock_context

        # Act & Assert
        with self.assertRaises(UserException) as context:
            _stop_durable_execution(self.test_execution_id)
        self.assertEqual(str(context.exception), "Lambda client error")


class TestLocalExecutionStopCliIntegration(TestCase):
    """Integration tests for CLI command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_execution_id = "c63eec67-3415-4eb4-a495-116aa3a86278"

    @patch("samcli.commands.local.execution.stop.cli._stop_durable_execution")
    def test_cli_integration_success(self, mock_stop_execution):
        """Test full CLI integration with successful response"""
        # Act
        result = self.runner.invoke(cli, [self.test_execution_id])

        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertIn("🛑 Execution stopped:", result.output)
        self.assertIn(self.test_execution_id, result.output)

    @patch("samcli.commands.local.execution.stop.cli._stop_durable_execution")
    def test_cli_integration_error_handling(self, mock_stop_execution):
        """Test CLI integration with error handling"""
        # Arrange
        mock_stop_execution.side_effect = Exception("Test error")

        # Act
        result = self.runner.invoke(cli, [self.test_execution_id])

        # Assert
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Test error", result.output)
