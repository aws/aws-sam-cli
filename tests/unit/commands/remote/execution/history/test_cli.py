import unittest
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.remote.execution.history.cli import cli, do_cli
from samcli.commands.exceptions import UserException


class TestRemoteExecutionHistory(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Get execution history of a durable function execution", result.output)

    @patch("samcli.commands.remote.execution.history.cli.do_cli")
    def test_cli_with_durable_execution_arn(self, mock_do_cli):
        mock_do_cli.return_value = True

        result = self.runner.invoke(
            cli,
            [
                "arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/durable-execution/my-execution-name/my-execution-id",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        mock_do_cli.assert_called_once()

    def test_cli_missing_required_arg(self):
        result = self.runner.invoke(cli, [])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)

    @patch("samcli.commands.remote.execution.history.cli.get_boto_client_provider_from_session_with_config")
    @patch("samcli.commands.remote.execution.history.cli.Session")
    @patch("samcli.commands.remote.execution.history.cli.DurableFunctionsClient")
    @patch("samcli.commands.remote.execution.history.cli.click.echo")
    def test_do_cli_success(self, mock_echo, mock_durable_client_class, mock_session_class, mock_get_client_provider):
        # Setup mocks
        mock_ctx = Mock()
        mock_ctx.region = "us-east-1"
        mock_ctx.profile = "default"

        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_client_provider = Mock()
        mock_get_client_provider.return_value = mock_client_provider

        mock_lambda_client = Mock()
        mock_client_provider.return_value = mock_lambda_client

        mock_durable_client = Mock()
        mock_durable_client_class.return_value = mock_durable_client
        mock_durable_client.get_durable_execution_history.return_value = {
            "Events": [{"EventType": "ExecutionStarted", "EventId": 1, "EventTimestamp": "2023-01-01T00:00:00Z"}]
        }

        # Call function
        do_cli(mock_ctx, "test-arn", "json")

        # Verify calls
        mock_session_class.assert_called_once_with(profile_name="default", region_name="us-east-1")
        mock_get_client_provider.assert_called_once_with(mock_session)
        mock_client_provider.assert_called_once_with("lambda")
        mock_durable_client_class.assert_called_once_with(mock_lambda_client)
        mock_durable_client.get_durable_execution_history.assert_called_once_with("test-arn")
        mock_echo.assert_called_once()

    @patch("samcli.commands.remote.execution.history.cli.get_boto_client_provider_from_session_with_config")
    @patch("samcli.commands.remote.execution.history.cli.Session")
    @patch("samcli.commands.remote.execution.history.cli.DurableFunctionsClient")
    def test_do_cli_exception(self, mock_durable_client_class, mock_session_class, mock_get_client_provider):
        # Setup mocks
        mock_ctx = Mock()
        mock_ctx.region = "us-east-1"
        mock_ctx.profile = "default"

        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_client_provider = Mock()
        mock_get_client_provider.return_value = mock_client_provider

        mock_lambda_client = Mock()
        mock_client_provider.return_value = mock_lambda_client

        mock_durable_client_class.side_effect = Exception("Test error")

        # Call function and expect exception
        with self.assertRaises(UserException) as cm:
            do_cli(mock_ctx, "test-arn", "json")

        self.assertEqual(str(cm.exception), "Test error")
