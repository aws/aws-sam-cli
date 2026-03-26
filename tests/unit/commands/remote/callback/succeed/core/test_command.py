import unittest
from unittest.mock import Mock, patch

from samcli.commands.remote.callback.succeed.core.command import RemoteCallbackSucceedCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestRemoteCallbackSucceedCommand(unittest.TestCase):
    @patch.object(RemoteCallbackSucceedCommand, "get_params")
    def test_remote_callback_succeed_options_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote callback succeed"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        mock_get_params.return_value = [
            MockParams(rv=("CALLBACK_ID", ""), name="callback_id"),
            MockParams(rv=("--output", ""), name="output"),
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--profile", ""), name="profile"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteCallbackSucceedCommand(name="succeed", description="Test description", requires_credentials=False)
        expected_output = {
            "Description": [
                ("Test description\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", ""), ("--profile", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", "")],
            "Callback Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "Send success callback with no result": [
                ("", ""),
                ("$ sam remote callback succeed my-callback-id\x1b[0m", ""),
            ],
            "Send success callback with result": [
                ("", ""),
                ("$ sam remote callback succeed my-callback-id --result 'Task completed successfully'\x1b[0m", ""),
            ],
        }
        cmd.format_options(ctx, formatter)
        self.assertEqual(expected_output, formatter.data)

    def test_format_examples(self):
        ctx = Mock()
        ctx.command_path = "sam remote callback succeed"
        formatter = MockFormatter(scrub_text=True)

        cmd = RemoteCallbackSucceedCommand(name="succeed", description="Test description", requires_credentials=False)
        cmd.format_examples(ctx, formatter)

        self.assertIn("Examples", formatter.data)
