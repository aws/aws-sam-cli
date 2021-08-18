import click

from unittest import TestCase
from installer.pyinstaller import hidden_imports
from samcli.cli.command import BaseCommand


class TestPyinstallerImportCommands(TestCase):
    def setUp(self):
        pass

    def test_hook_contains_all_default_command_packages(self):
        cmd = BaseCommand()
        command_package_names = cmd._commands.values()

        for name in command_package_names:
            self.assertIn(name, hidden_imports.SAM_CLI_HIDDEN_IMPORTS)

    def test_hook_not_contain_self_defined_command_packages(self):
        cmd = BaseCommand(cmd_packages=["my.self.defined.package"])
        command_package_names = cmd._commands.values()

        for name in command_package_names:
            self.assertNotIn(name, hidden_imports.SAM_CLI_HIDDEN_IMPORTS)
