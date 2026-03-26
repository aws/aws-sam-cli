import unittest
from unittest.mock import Mock, patch

from samcli.commands.remote.execution.get.core.command import RemoteExecutionGetCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestRemoteExecutionGetCommand(unittest.TestCase):

    @patch.object(RemoteExecutionGetCommand, "get_params")
    def test_get_options_get_durable_execution_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote execution get"
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

        cmd = RemoteExecutionGetCommand(name="get", description="Test description", requires_credentials=False)
        expected_output = {
            "Description": [
                ("Test description\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "Get execution details": [
                (
                    "$ sam remote execution get 'arn:aws:lambda:us-east-1:123456789012:function:my-function:$LATEST/durable-execution/c63eec67-3415-4eb4-a495-116aa3a86278/1d454231-a3ad-3694-aa03-c917c175db55'\x1b[0m",
                    "",
                ),
            ],
            "Get execution details in JSON format": [
                (
                    "$ sam remote execution get 'arn:aws:lambda:us-east-1:123456789012:function:my-function:$LATEST/durable-execution/c63eec67-3415-4eb4-a495-116aa3a86278/1d454231-a3ad-3694-aa03-c917c175db55' --format json\x1b[0m",
                    "",
                ),
            ],
            "Note": [
                (
                    "\n  You must ensure that control characters in the execution ARN such as $ are escaped properly when using shell commands.",
                    "",
                )
            ],
            "Acronyms": [("ARN", "")],
            "Formatting Options": [("", ""), ("--format", ""), ("", "")],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", ""), ("--profile", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
        }
        cmd.format_options(ctx, formatter)
        self.assertEqual(expected_output, formatter.data)

    def test_format_examples(self):
        ctx = Mock()
        ctx.command_path = "sam remote execution get"
        formatter = MockFormatter(scrub_text=True)

        cmd = RemoteExecutionGetCommand(name="get", description="Test description", requires_credentials=False)
        cmd.format_examples(ctx, formatter)

        self.assertIn("Examples", formatter.data)
        self.assertIn("Get execution details", formatter.data)
        self.assertIn("Get execution details in JSON format", formatter.data)
