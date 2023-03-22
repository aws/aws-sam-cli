from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.sync.core.formatters import SyncCommandHelpTextFormatter


class TestSyncCommandHelpTextFormatter(TestCase):
    def test_sync_formatter(self):
        self.formatter = SyncCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
