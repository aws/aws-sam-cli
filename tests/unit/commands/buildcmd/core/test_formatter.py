from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.build.core.formatters import BuildCommandHelpTextFormatter


class TestBuildCommandHelpTextFormatter(TestCase):
    def test_build_formatter(self):
        self.formatter = BuildCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
