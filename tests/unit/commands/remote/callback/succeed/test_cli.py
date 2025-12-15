import unittest
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.remote.callback.succeed.cli import cli, do_cli


class TestRemoteCallbackSucceedCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Send a callback success", result.output)

    @patch("samcli.commands.remote.callback.succeed.cli.do_cli")
    def test_cli_with_callback_id(self, mock_do_cli):
        mock_do_cli.return_value = True

        result = self.runner.invoke(cli, ["my-callback-id"])

        self.assertEqual(result.exit_code, 0)
        mock_do_cli.assert_called_once()

    def test_cli_missing_required_arg(self):
        result = self.runner.invoke(cli, [])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing argument", result.output)

    @patch("samcli.commands.remote.callback.succeed.cli.get_boto_client_provider_from_session_with_config")
    @patch("samcli.commands.remote.callback.succeed.cli.Session")
    @patch("samcli.commands.remote.callback.succeed.cli.DurableFunctionsClient")
    @patch("samcli.commands.remote.callback.succeed.cli.format_callback_success_message")
    @patch("samcli.commands.remote.callback.succeed.cli.click.echo")
    def test_do_cli_success(
        self, mock_echo, mock_get_message, mock_durable_client_class, mock_session_class, mock_get_client_provider
    ):
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

        expected_message = "✅ Callback success sent for ID: test-id"
        mock_get_message.return_value = expected_message

        do_cli(mock_ctx, "test-id", None)

        mock_session_class.assert_called_once_with(profile_name="default", region_name="us-east-1")
        mock_get_client_provider.assert_called_once_with(mock_session)
        mock_client_provider.assert_called_once_with("lambda")
        mock_durable_client_class.assert_called_once_with(mock_lambda_client)
        mock_durable_client.send_callback_success.assert_called_once()
        mock_get_message.assert_called_once_with("test-id", None)
        mock_echo.assert_called_once_with(expected_message)

    @patch("samcli.commands.remote.callback.succeed.cli.get_boto_client_provider_from_session_with_config")
    @patch("samcli.commands.remote.callback.succeed.cli.Session")
    @patch("samcli.commands.remote.callback.succeed.cli.DurableFunctionsClient")
    def test_do_cli_exception(self, mock_durable_client_class, mock_session_class, mock_get_client_provider):
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

        with self.assertRaises(UserException) as cm:
            do_cli(mock_ctx, "test-id", None)

        self.assertEqual(str(cm.exception), "Test error")
