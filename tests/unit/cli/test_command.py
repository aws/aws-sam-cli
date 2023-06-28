from contextlib import contextmanager

import click

from unittest import TestCase
from unittest.mock import Mock, patch, call
from samcli.cli.command import BaseCommand
from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.root.command_list import SAM_CLI_COMMANDS


class MockParams:
    def __init__(self, rv):
        self.rv = rv

    def get_help_record(self, ctx):
        return self.rv


class MockContextManager:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self, *args, **kwargs):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockFormatter:
    def __init__(self, scrub_text=False):
        self.data = dict()
        self.scrub_text = scrub_text

    @contextmanager
    def section(self, name):
        self.data[name] = []
        try:
            yield
        finally:
            pass

    @contextmanager
    def indented_section(self, name, extra_indents=0):
        self.data[name] = []
        try:
            yield
        finally:
            pass

    def write_rd(self, rows, col_max=None):
        self.data[list(self.data.keys())[-1]] = [(row.name, "" if self.scrub_text else row.text) for row in rows]


class TestBaseCommand(TestCase):
    def setUp(self):
        self.packages = ["a.b.cmd1", "foo.cmd2", "cmd3"]

    def test_must_inherit(self):
        cmd = BaseCommand()
        self.assertTrue(isinstance(cmd, click.MultiCommand))

    def test_check_formatter(self):
        cmd = BaseCommand()
        self.assertEqual(cmd.context_class.formatter_class, RootCommandHelpTextFormatter)

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

    @patch.object(BaseCommand, "format_commands")
    @patch.object(BaseCommand, "get_params")
    def test_get_options_root_command_text(self, mock_get_params, mock_format_commands):
        ctx = Mock()
        formatter = MockFormatter(scrub_text=True)
        mock_get_params.return_value = [MockParams(rv=("--region", "Region"))]

        cmd = BaseCommand(cmd_packages=self.packages)
        expected_output = {"Options": [("", ""), ("--region", "")], "Examples": [("", ""), ("Get Started:", "")]}

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)

    def test_get_command_root_command_text(self):
        ctx = Mock()
        formatter = MockFormatter()
        cmd = BaseCommand()
        expected_output = {
            "Commands": [],
            "Learn": [("docs", "docs command output")],
            "Create an App": [("init", "init command output")],
            "Develop your App": [
                ("build", "build command output"),
                ("local", "local command output"),
                ("validate", "validate command output"),
                ("sync", "sync command output"),
                ("remote", "remote command output"),
            ],
            "Deploy your App": [("package", "package command output"), ("deploy", "deploy command output")],
            "Monitor your App": [("logs", "logs command output"), ("traces", "traces command output")],
            "And More": [
                ("list", "list command output"),
                ("delete", "delete command output"),
                ("pipeline", "pipeline command output"),
                ("publish", "publish command output"),
            ],
        }
        with patch.dict(
            SAM_CLI_COMMANDS,
            {
                "init": "init command output",
                "build": "build command output",
                "local": "local command output",
                "validate": "validate command output",
                "sync": "sync command output",
                "remote": "remote command output",
                "package": "package command output",
                "deploy": "deploy command output",
                "logs": "logs command output",
                "traces": "traces command output",
                "list": "list command output",
                "delete": "delete command output",
                "pipeline": "pipeline command output",
                "publish": "publish command output",
                "docs": "docs command output",
            },
        ):
            cmd.format_commands(ctx, formatter)
            self.assertEqual(formatter.data, expected_output)
