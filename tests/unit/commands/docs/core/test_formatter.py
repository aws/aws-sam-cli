from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.docs.core.formatter import DocsCommandHelpTextFormatter


class TestDocsCommandHelpTextFormatter(TestCase):
    def test_docs_formatter(self):
        formatter = DocsCommandHelpTextFormatter()
        self.assertTrue(formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(formatter.modifiers[0], BaseLineRowModifier)
