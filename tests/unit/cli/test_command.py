import click

from unittest import TestCase
from unittest.mock import Mock, patch, call
from samcli.cli.command import BaseCommand


class TestBaseCommand(TestCase):
    def setUp(self):

        self.packages = ["a.b.cmd1", "foo.cmd2", "cmd3"]

    def test_must_inherit(self):

        cmd = BaseCommand()
        self.assertTrue(isinstance(cmd, click.MultiCommand))

    def test_set_commands_must_extract_command_name(self):
        expected = {"cmd1": "a.b.cmd1", "cmd2": "foo.cmd2", "cmd3": "cmd3"}

        result = BaseCommand._set_commands(self.packages)
        self.assertEqual(result, expected)

    def test_list_commands_must_return_commands_name(self):
        expected = ["cmd1", "cmd2", "cmd3"].sort()

        cmd = BaseCommand(cmd_packages=self.packages)
        result = cmd.list_commands(ctx=None)
        self.assertEqual(result.sort(), expected)

    @patch("samcli.cli.command.importlib")
    def test_get_command_must_return_command_module(self, importlib_mock):
        module_mock = Mock()
        module_mock.cli = Mock()
        ctx = Mock()
        ctx.obj = Mock()

        importlib_mock.import_module = Mock()
        importlib_mock.import_module.return_value = module_mock

        cmd = BaseCommand(cmd_packages=self.packages)

        result = cmd.get_command(ctx, "cmd1")
        self.assertEqual(result, module_mock.cli)

        result = cmd.get_command(ctx, "cmd2")
        self.assertEqual(result, module_mock.cli)

        result = cmd.get_command(ctx, "cmd3")
        self.assertEqual(result, module_mock.cli)

        # Library to import the modules must be called three times
        importlib_mock.import_module.assert_has_calls([call("a.b.cmd1"), call("foo.cmd2"), call("cmd3")])

    def test_get_command_must_skip_unknown_commands(self):
        ctx = Mock()
        ctx.obj = Mock()

        cmd = BaseCommand(cmd_packages=self.packages)
        result = cmd.get_command(ctx, "unknown_command")

        self.assertEqual(result, None, "must not return a command")

    @patch("samcli.cli.command.importlib")
    def test_get_command_must_skip_on_exception_loading_module(self, importlib_mock):
        ctx = Mock()
        ctx.obj = Mock()

        cmd = BaseCommand(cmd_packages=self.packages)

        importlib_mock.import_module = Mock()
        importlib_mock.import_module.side_effect = ImportError()

        result = cmd.get_command(ctx, "cmd1")
        self.assertEqual(result, None, "must not return a command")

    @patch("samcli.cli.command.importlib")
    def test_get_command_must_skip_on_absence_of_cli_method(self, importlib_mock):
        ctx = Mock()
        ctx.obj = Mock()

        cmd = BaseCommand(cmd_packages=self.packages)

        importlib_mock.import_module = Mock()
        importlib_mock.import_module.return_value = {}  # Returned Module does *not* have 'cli' property

        result = cmd.get_command(ctx, "cmd1")
        self.assertEqual(result, None, "must not return a command")

    @patch("samcli.cli.command.importlib")
    def test_get_command_root_command(self, importlib_mock):
        ctx = Mock()
        ctx.obj = None

        cmd = BaseCommand(cmd_packages=self.packages)

        importlib_mock.import_module = Mock()
        importlib_mock.import_module.return_value = {}  # Returned Module does *not* have 'cli' property

        cmd.get_command(ctx, "cmd1")
        self.assertEqual(importlib_mock.import_module.call_count, 0)
