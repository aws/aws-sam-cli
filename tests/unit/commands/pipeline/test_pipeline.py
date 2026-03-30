"""
Unit tests for sam pipeline CLI group
"""

import unittest
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.pipeline.pipeline import cli


class TestPipelineCliGroup(unittest.TestCase):
    """Test cases for pipeline CLI group functionality"""

    def setUp(self):
        self.runner = CliRunner()

    def test_pipeline_group_help(self):
        """Test that pipeline group shows help and lists subcommands"""
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Manage the continuous delivery of the application", result.output)
        self.assertIn("bootstrap", result.output)
        self.assertIn("init", result.output)

    @parameterized.expand([("bootstrap",), ("init",)])
    def test_subcommand_help(self, command):
        """Test that subcommands can be loaded and show help"""
        result = self.runner.invoke(cli, [command, "--help"])
        self.assertEqual(result.exit_code, 0)
