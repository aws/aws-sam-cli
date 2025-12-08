"""
Unit tests for sam list CLI group
"""

import unittest
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.list.list import cli


class TestListCliGroup(unittest.TestCase):
    """Test cases for list CLI group functionality"""

    def setUp(self):
        self.runner = CliRunner()

    def test_list_group_help(self):
        """Test that list group shows help and lists subcommands"""
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Get local and deployed state of serverless application", result.output)
        self.assertIn("endpoints", result.output)
        self.assertIn("resources", result.output)
        self.assertIn("stack-outputs", result.output)

    @parameterized.expand([("endpoints",), ("resources",), ("stack-outputs",)])
    def test_subcommand_help(self, command):
        """Test that subcommands can be loaded and show help"""
        result = self.runner.invoke(cli, [command, "--help"])
        self.assertEqual(result.exit_code, 0)
