import unittest
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.remote.execution.get.cli import cli, do_cli
from samcli.commands.exceptions import UserException


class TestRemoteExecutionGetCliCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Get details of a durable execution", result.output)

    @patch("samcli.commands.remote.execution.get.cli.do_cli")
    def test_cli_with_durable_execution_arn(self, mock_do_cli):
        mock_do_cli.return_value = True

        result = self.runner.invoke(
            cli,
            [
                "arn:aws:lambda:us-east-1:123456789012:function:my-function:1/durable-execution/c63eec67-3415-4eb4-a495-116aa3a86278/1d454231-a3ad-3694-aa03-c917c175db55",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        mock_do_cli.assert_called_once()

    def test_cli_missing_required_arg(self):
        result = self.runner.invoke(cli, [])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)

    @patch("samcli.commands.remote.execution.get.cli.get_boto_client_provider_from_session_with_config")
    @patch("samcli.commands.remote.execution.get.cli.Session")
    @patch("samcli.commands.remote.execution.get.cli.DurableFunctionsClient")
    @patch("samcli.commands.remote.execution.get.cli.format_execution_details")
    @patch("click.echo")
    def test_do_cli_success(
        self,
        mock_echo,
        mock_format_execution_details,
        mock_durable_client_class,
        mock_session_class,
        mock_get_client_provider,
    ):
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
        execution_result = {"ExecutionArn": "test-arn", "Status": "SUCCEEDED"}
        mock_durable_client.get_durable_execution.return_value = execution_result

        # Call function with default format
        do_cli(mock_ctx, "test-arn", "summary")

        # Verify calls
        mock_session_class.assert_called_once_with(profile_name="default", region_name="us-east-1")
        mock_get_client_provider.assert_called_once_with(mock_session)
        mock_client_provider.assert_called_once_with("lambda")
        mock_durable_client_class.assert_called_once_with(mock_lambda_client)
        mock_durable_client.get_durable_execution.assert_called_once_with("test-arn")
        mock_format_execution_details.assert_called_once_with("test-arn", execution_result, "summary")
        mock_echo.assert_called_once()

    @patch("samcli.commands.remote.execution.get.cli.get_boto_client_provider_from_session_with_config")
    @patch("samcli.commands.remote.execution.get.cli.Session")
    @patch("samcli.commands.remote.execution.get.cli.DurableFunctionsClient")
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
            do_cli(mock_ctx, "test-arn", "summary")

        self.assertEqual(str(cm.exception), "Test error")
