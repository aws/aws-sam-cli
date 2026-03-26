from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.common.formatters import CommandHelpTextFormatter
from samcli.commands.remote.core.options import ALL_OPTIONS


class TestRemoteExecutionBaseFormatter(TestCase):
    def test_remote_execution_formatter(self):
        formatter = CommandHelpTextFormatter(ALL_OPTIONS)
        self.assertTrue(formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(formatter.modifiers[0], BaseLineRowModifier)
        self.assertEqual(formatter.ADDITIVE_JUSTIFICATION, 17)
