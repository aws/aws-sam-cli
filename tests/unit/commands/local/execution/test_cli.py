"""
Unit tests for sam local execution CLI group
"""

import unittest
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.local.execution.cli import cli


class TestLocalExecutionCliGroup(unittest.TestCase):
    """Test cases for local execution CLI group functionality"""

    def setUp(self):
        self.runner = CliRunner()

    def test_execution_group_help(self):
        """Test that execution group shows help and lists subcommands"""
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Manage durable function executions", result.output)
        self.assertIn("get", result.output)
        self.assertIn("history", result.output)
        self.assertIn("stop", result.output)

    @parameterized.expand(
        [
            ("get", "Get details of a durable function execution"),
            ("history", "Get execution history"),
            ("stop", "Stop a durable function execution"),
        ]
    )
    def test_subcommand_help(self, command, expected_text):
        """Test that subcommands can be loaded and show help"""
        result = self.runner.invoke(cli, [command, "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(expected_text, result.output)
        self.assertIn("DURABLE_EXECUTION_ARN", result.output)
