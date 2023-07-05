from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.logs.core.formatters import LogsCommandHelpTextFormatter


class TestLogsCommandHelpTextFormatter(TestCase):
    def test_logs_formatter(self):
        self.formatter = LogsCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
