"""
Unit tests for sam remote test-event CLI group
"""

import unittest
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.remote.test_event.test_event import cli


class TestTestEventCliGroup(unittest.TestCase):
    """Test cases for test-event CLI group functionality"""

    def setUp(self):
        self.runner = CliRunner()

    def test_test_event_group_help(self):
        """Test that test-event group shows help and lists subcommands"""
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Manage remote test events", result.output)
        self.assertIn("delete", result.output)
        self.assertIn("get", result.output)
        self.assertIn("put", result.output)
        self.assertIn("list", result.output)

    @parameterized.expand([("delete",), ("get",), ("put",), ("list",)])
    def test_subcommand_help(self, command):
        """Test that subcommands can be loaded and show help"""
        result = self.runner.invoke(cli, [command, "--help"])
        self.assertEqual(result.exit_code, 0)
