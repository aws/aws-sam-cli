from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.init.core.formatters import InitCommandHelpTextFormatter


class TestInitCommandHelpTextFormatter(TestCase):
    def test_init_formatter(self):
        self.formatter = InitCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
