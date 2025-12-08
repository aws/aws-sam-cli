import unittest
from unittest.mock import Mock, patch

from samcli.commands.remote.execution.stop.core.command import RemoteExecutionStopCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestRemoteExecutionStopCommand(unittest.TestCase):

    @patch.object(RemoteExecutionStopCommand, "get_params")
    def test_remote_execution_stop_options_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam remote execution stop"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)
        # NOTE: One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("DURABLE_EXECUTION_ARN", ""), name="durable_execution_arn"),
            MockParams(rv=("--error-message", ""), name="error_message"),
            MockParams(rv=("--error-type", ""), name="error_type"),
            MockParams(rv=("--error-data", ""), name="error_data"),
            MockParams(rv=("--stack-trace", ""), name="stack_trace"),
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--profile", ""), name="profile"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--debug", ""), name="debug"),
        ]

        cmd = RemoteExecutionStopCommand(name="stop", description="Test description", requires_credentials=False)
        expected_output = {
            "Description": [
                ("Test description\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m", "")
            ],
            "Examples": [],
            "Stop execution without error details": [
                (
                    "$ sam remote execution stop arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/durable-execution/my-execution-name/my-execution-id\x1b[0m",
                    "",
                ),
            ],
            "Stop execution with error message and type": [
                (
                    '$ sam remote execution stop arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/durable-execution/my-execution-name/my-execution-id --error-message "Execution cancelled" --error-type "UserCancellation"\x1b[0m',
                    "",
                ),
            ],
            "Stop execution with full error details and stack trace": [
                (
                    '$ sam remote execution stop arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/durable-execution/my-execution-name/my-execution-id --error-message "Task failed" --error-type "TaskFailure" --error-data \'{"reason":"timeout"}\' --stack-trace "at function1()" --stack-trace "at function2()"\x1b[0m',
                    "",
                ),
            ],
            "Acronyms": [("ARN", "")],
            "Stop Options": [
                ("", ""),
                ("--error-message", ""),
                ("", ""),
                ("--error-type", ""),
                ("", ""),
                ("--error-data", ""),
                ("", ""),
                ("--stack-trace", ""),
                ("", ""),
            ],
            "AWS Credential Options": [("", ""), ("--region", ""), ("", ""), ("--profile", ""), ("", "")],
            "Configuration Options": [("", ""), ("--config-file", ""), ("", "")],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", "")],
        }
        cmd.format_options(ctx, formatter)
        self.assertEqual(expected_output, formatter.data)

    def test_format_examples(self):
        ctx = Mock()
        ctx.command_path = "sam remote execution stop"
        formatter = MockFormatter(scrub_text=True)

        cmd = RemoteExecutionStopCommand(name="stop", description="Test description", requires_credentials=False)
        cmd.format_examples(ctx, formatter)

        self.assertIn("Examples", formatter.data)
        self.assertIn("Stop execution without error details", formatter.data)
        self.assertIn("Stop execution with error message and type", formatter.data)
        self.assertIn("Stop execution with full error details and stack trace", formatter.data)
