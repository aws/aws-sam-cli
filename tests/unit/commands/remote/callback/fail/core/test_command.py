import unittest
from unittest.mock import Mock, patch

from samcli.commands.remote.callback.fail.core.command import RemoteCallbackFailCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestRemoteCallbackFailCommand(unittest.TestCase):
    @patch.object(RemoteCallbackFailCommand, "get_params")
    def test_remote_callback_fail_options_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote callback fail"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        mock_get_params.return_value = [
            MockParams(rv=("CALLBACK_ID", ""), name="callback_id"),
            MockParams(rv=("--error-data", ""), name="error_data"),
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--profile", ""), name="profile"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteCallbackFailCommand(name="fail", description="Test description", requires_credentials=False)
        expected_output = {
            "Description": [
                ("Test description\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", ""), ("--profile", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", "")],
            "Callback Options": [("", ""), ("--error-data", ""), ("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Send failure callback with no parameters": [
                ("", ""),
                ("$ sam remote callback fail my-callback-id\x1b[0m", ""),
            ],
            "Send failure callback with error message": [
                ("", ""),
                ("$ sam remote callback fail my-callback-id --error-message 'Task failed'\x1b[0m", ""),
            ],
            "Send failure callback with all parameters": [
                ("", ""),
                (
                    "$ sam remote callback fail my-callback-id --error-message 'Task failed' --error-type 'ValidationError' --stack-trace 'at line 42' --error-data '{\"code\": 500}'\x1b[0m",
                    "",
                ),
            ],
        }
        cmd.format_options(ctx, formatter)
        self.assertEqual(expected_output, formatter.data)

    def test_format_examples(self):
        ctx = Mock()
        ctx.command_path = "sam remote callback fail"
        formatter = MockFormatter(scrub_text=True)

        cmd = RemoteCallbackFailCommand(name="fail", description="Test description", requires_credentials=False)
        cmd.format_examples(ctx, formatter)

        self.assertIn("Examples", formatter.data)
