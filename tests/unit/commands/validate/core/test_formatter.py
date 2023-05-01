from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.validate.core.formatters import ValidateCommandHelpTextFormatter


class TestValidateCommandHelpTextFormatter(TestCase):
    def test_validate_formatter(self):
        self.formatter = ValidateCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
