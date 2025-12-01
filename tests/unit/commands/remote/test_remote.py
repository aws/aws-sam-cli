"""
Unit tests for sam remote CLI group
"""

import unittest
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.remote.remote import cli


class TestRemoteCliGroup(unittest.TestCase):
    """Test cases for remote CLI group functionality"""

    def setUp(self):
        self.runner = CliRunner()

    def test_remote_group_help(self):
        """Test that remote group shows help and lists subcommands"""
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Interact with your Serverless application in the cloud", result.output)
        self.assertIn("invoke", result.output)
        self.assertIn("test-event", result.output)

    @parameterized.expand([("invoke",), ("test-event",)])
    def test_subcommand_help(self, command):
        """Test that subcommands can be loaded and show help"""
        result = self.runner.invoke(cli, [command, "--help"])
        self.assertEqual(result.exit_code, 0)
