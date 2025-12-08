"""
Unit tests for execution get core command
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.execution.get.core.command import LocalExecutionGetCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalExecutionGetCommand(TestCase):
    """Test cases for LocalExecutionGetCommand"""

    @patch.object(LocalExecutionGetCommand, "get_params")
    def test_format_options(self, mock_get_params):
        """Test format_options method"""
        # Arrange
        ctx = Mock()
        ctx.command_path = "sam local execution get"
        formatter = MockFormatter(scrub_text=True)

        mock_get_params.return_value = [
            MockParams(rv=("durable_execution_arn", "Durable execution ARN"), name="durable_execution_arn"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--help", ""), name="help"),
        ]

        command = LocalExecutionGetCommand(name="get", description="Get durable function execution details")
        expected_output = {
            "Description": [
                (
                    "Get durable function execution details\x1b[1m\n  This command may not require access to AWS credentials.\x1b[0m",
                    "",
                )
            ],
            "Examples": [],
            "Get execution details": [
                (
                    "$ sam local execution get c63eec67-3415-4eb4-a495-116aa3a86278\x1b[0m",
                    "",
                ),
            ],
            "Get execution details in JSON format": [
                (
                    "$ sam local execution get c63eec67-3415-4eb4-a495-116aa3a86278 --format json\x1b[0m",
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
