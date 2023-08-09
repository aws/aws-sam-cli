from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.package.core.formatters import PackageCommandHelpTextFormatter


class TestPackageCommandHelpTextFormatter(TestCase):
    def test_deploy_formatter(self):
        self.formatter = PackageCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
