from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.remote.invoke.core.formatters import RemoteInvokeCommandHelpTextFormatter


class TestRemoteInvokeCommandHelpTextFormatter(TestCase):
    def test_remote_invoke_formatter(self):
        self.formatter = RemoteInvokeCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
