"""
Unit tests for LazyGroup functionality
"""

import unittest
from unittest.mock import Mock, patch

import click
from click.testing import CliRunner

from samcli.cli.lazy_group import LazyGroup


class TestLazyGroup(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_lazy_group_lists_commands(self):
        """Test that LazyGroup correctly lists available commands"""

        @click.group(
            cls=LazyGroup,
            lazy_subcommands={
                "cmd1": "fake.module.cmd1",
                "cmd2": "fake.module.cmd2",
            },
        )
        def test_group():
            pass

        # Should list lazy commands
        commands = test_group.list_commands(None)
        self.assertIn("cmd1", commands)
        self.assertIn("cmd2", commands)

    @patch("samcli.cli.lazy_group.importlib.import_module")
    def test_lazy_group_loads_command_on_demand(self, mock_import):
        """Test that LazyGroup only imports modules when commands are accessed"""
        # Mock the imported module and command
        mock_module = Mock()
        mock_command = Mock(spec=click.Command)
        mock_module.cli = mock_command
        mock_import.return_value = mock_module

        @click.group(
            cls=LazyGroup,
            lazy_subcommands={
                "test-cmd": "fake.module.cli",
            },
        )
        def test_group():
            pass

        # Import should not happen until command is accessed
        mock_import.assert_not_called()

        # Access the command
        result = test_group.get_command(None, "test-cmd")

        # Now import should have happened
        mock_import.assert_called_once_with("fake.module")
        self.assertEqual(result, mock_command)

    @patch("samcli.cli.lazy_group.importlib.import_module")
    def test_lazy_group_handles_missing_command(self, mock_import):
        """Test that LazyGroup handles requests for non-existent commands"""

        @click.group(
            cls=LazyGroup,
            lazy_subcommands={
                "existing-cmd": "fake.module.cli",
            },
        )
        def test_group():
            pass

        # Request non-existent command
        result = test_group.get_command(None, "non-existent")

        # Should return None and not attempt import
        self.assertIsNone(result)
        mock_import.assert_not_called()

    @patch("samcli.cli.lazy_group.importlib.import_module")
    def test_lazy_group_handles_import_error(self, mock_import):
        """Test that LazyGroup handles import errors gracefully"""
        mock_import.side_effect = ImportError("Module not found")

        @click.group(
            cls=LazyGroup,
            lazy_subcommands={
                "broken-cmd": "nonexistent.module.cli",
            },
        )
        def test_group():
            pass

        # Should raise ClickException when import fails
        with self.assertRaises(click.ClickException) as cm:
            test_group.get_command(None, "broken-cmd")

        self.assertIn("Failed to load command 'broken-cmd'", str(cm.exception))

    @patch("samcli.cli.lazy_group.importlib.import_module")
    def test_lazy_group_validates_command_object(self, mock_import):
        """Test that LazyGroup validates imported objects are Click commands"""
        # Mock module with non-command object
        mock_module = Mock()
        mock_module.cli = "not a command"
        mock_import.return_value = mock_module

        @click.group(
            cls=LazyGroup,
            lazy_subcommands={
                "invalid-cmd": "fake.module.cli",
            },
        )
        def test_group():
            pass

        # Should raise ClickException for non-command objects
        with self.assertRaises(click.ClickException) as cm:
            test_group.get_command(None, "invalid-cmd")

        self.assertIn("non-command object", str(cm.exception))
