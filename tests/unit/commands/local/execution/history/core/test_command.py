"""
Unit tests for execution history core command
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.execution.history.core.command import LocalExecutionHistoryCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalExecutionHistoryCommand(TestCase):
    """Test cases for LocalExecutionHistoryCommand"""

    @patch.object(LocalExecutionHistoryCommand, "get_params")
    def test_format_options(self, mock_get_params):
        """Test format_options method"""
        # Arrange
        ctx = Mock()
        ctx.command_path = "sam local execution history"
        formatter = MockFormatter(scrub_text=True)

        mock_get_params.return_value = [
            MockParams(rv=("durable_execution_arn", "Durable execution ARN"), name="durable_execution_arn"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--help", ""), name="help"),
        ]

        command = LocalExecutionHistoryCommand(name="history", description="Get durable function execution history")
        expected_output = {
            "Description": [
                (
                    "Get durable function execution history\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m",
                    "",
                )
            ],
            "Examples": [],
            "Get execution history": [
                (
                    "$ sam local execution history c63eec67-3415-4eb4-a495-116aa3a86278\x1b[0m",
                    "",
                ),
            ],
            "Get execution history in JSON format": [
                (
                    "$ sam local execution history c63eec67-3415-4eb4-a495-116aa3a86278 --format json\x1b[0m",
                    "",
                ),
            ],
            "Formatting Options": [("", "")],
            "Beta Options": [("", "")],
            "Other Options": [("", ""), ("--debug", ""), ("", ""), ("--help", ""), ("", "")],
        }

        # Act
        command.format_options(ctx, formatter)

        # Assert
        self.assertEqual(formatter.data, expected_output)
