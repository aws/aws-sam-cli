import unittest
from unittest.mock import Mock, patch

from samcli.commands.remote.execution.history.core.command import RemoteExecutionHistoryCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestRemoteExecutionHistoryCommand(unittest.TestCase):

    @patch.object(RemoteExecutionHistoryCommand, "get_params")
    def test_remote_execution_history_options_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote execution history"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE: One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("DURABLE_EXECUTION_ARN", ""), name="durable_execution_arn"),
            MockParams(rv=("--format", ""), name="format"),
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--profile", ""), name="profile"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteExecutionHistoryCommand(name="history", description="Test description", requires_credentials=False)
        expected_output = {
            "Description": [
                ("Test description\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "Get execution history": [
                (
                    "$ sam remote execution history arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/durable-execution/my-execution-name/my-execution-id\x1b[0m",
                    "",
                ),
            ],
            "Get execution history in JSON format": [
                (
                    "$ sam remote execution history arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/durable-execution/my-execution-name/my-execution-id --format json\x1b[0m",
                    "",
                ),
            ],
            "Acronyms": [("ARN", "")],
            "Formatting Options": [("", ""), ("--format", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", ""), ("--profile", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }
        cmd.format_options(ctx, formatter)
        self.assertEqual(expected_output, formatter.data)

    def test_format_examples(self):
        ctx = Mock()
        ctx.command_path = "sam remote execution history"
        formatter = MockFormatter(scrub_text=True)

        cmd = RemoteExecutionHistoryCommand(name="history", description="Test description", requires_credentials=False)
        cmd.format_examples(ctx, formatter)

        self.assertIn("Examples", formatter.data)
        self.assertIn("Get execution history", formatter.data)
        self.assertIn("Get execution history in JSON format", formatter.data)
