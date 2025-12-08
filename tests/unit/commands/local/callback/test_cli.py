"""
Unit tests for sam local callback CLI group
"""

import unittest
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.local.callback.cli import cli


class TestLocalCallbackCliGroup(unittest.TestCase):
    """Test cases for local callback CLI group functionality"""

    def setUp(self):
        self.runner = CliRunner()

    def test_callback_group_help(self):
        """Test that callback group shows help and lists subcommands"""
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Send callbacks to durable function executions", result.output)
        self.assertIn("succeed", result.output)
        self.assertIn("fail", result.output)
        self.assertIn("heartbeat", result.output)

    @parameterized.expand(
        [
            ("succeed", "Send a success callback"),
            ("fail", "Send a failure callback"),
            ("heartbeat", "Send a heartbeat callback"),
        ]
    )
    def test_subcommand_help(self, command, expected_text):
        """Test that subcommands can be loaded and show help"""
        result = self.runner.invoke(cli, [command, "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(expected_text, result.output)
        self.assertIn("CALLBACK_ID", result.output)
