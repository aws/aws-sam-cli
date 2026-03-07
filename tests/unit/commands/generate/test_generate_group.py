"""Unit tests for generate command group"""

from unittest import TestCase
from unittest.mock import patch, Mock
from click.testing import CliRunner

from samcli.commands.generate.generate import cli


class TestGenerateCommandGroup(TestCase):
    """Test the generate command group"""

    def setUp(self):
        self.runner = CliRunner()

    def test_generate_command_help(self):
        """Test generate command shows help"""
        result = self.runner.invoke(cli, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Commands:", result.output)

    def test_generate_command_has_openapi_subcommand(self):
        """Test that openapi subcommand is registered"""
        result = self.runner.invoke(cli, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("openapi", result.output)
        self.assertIn("Generate OpenAPI specification", result.output)

    def test_generate_group_is_click_group(self):
        """Test that cli is a Click group"""
        self.assertTrue(hasattr(cli, "commands"))
        self.assertIn("openapi", cli.commands)
