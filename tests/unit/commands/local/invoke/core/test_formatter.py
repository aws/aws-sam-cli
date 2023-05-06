from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.local.invoke.core.formatters import InvokeCommandHelpTextFormatter


class TestLocalInvokeCommandHelpTextFormatter(TestCase):
    def test_local_invoke_formatter(self):
        self.formatter = InvokeCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
