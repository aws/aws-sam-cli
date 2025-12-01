"""
Unit tests for sam local CLI group
"""

import unittest
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.local.local import cli


class TestLocalCliGroup(unittest.TestCase):
    """Test cases for local CLI group functionality"""

    def setUp(self):
        self.runner = CliRunner()

    def test_local_group_help(self):
        """Test that local group shows help and lists subcommands"""
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Run your Serverless application locally", result.output)
        self.assertIn("invoke", result.output)
        self.assertIn("start-api", result.output)
        self.assertIn("start-lambda", result.output)
        self.assertIn("generate-event", result.output)

    @parameterized.expand([("invoke",), ("start-api",), ("start-lambda",), ("generate-event",)])
    def test_subcommand_help(self, command):
        """Test that subcommands can be loaded and show help"""
        result = self.runner.invoke(cli, [command, "--help"])
        self.assertEqual(result.exit_code, 0)
