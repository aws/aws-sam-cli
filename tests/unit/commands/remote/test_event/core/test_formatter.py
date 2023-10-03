from shutil import get_terminal_size
from unittest import TestCase
from parameterized import parameterized

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.remote.test_event.delete.core.formatters import RemoteTestEventDeleteCommandHelpTextFormatter
from samcli.commands.remote.test_event.get.core.formatters import RemoteTestEventGetCommandHelpTextFormatter
from samcli.commands.remote.test_event.list.core.formatters import RemoteTestEventListCommandHelpTextFormatter
from samcli.commands.remote.test_event.put.core.formatters import RemoteTestEventPutCommandHelpTextFormatter


class TestRemoteInvokeCommandHelpTextFormatter(TestCase):
    @parameterized.expand(
        [
            (RemoteTestEventDeleteCommandHelpTextFormatter,),
            (RemoteTestEventGetCommandHelpTextFormatter,),
            (RemoteTestEventListCommandHelpTextFormatter,),
            (RemoteTestEventPutCommandHelpTextFormatter,),
        ]
    )
    def test_remote_invoke_formatter(self, FormatterClass):
        self.formatter = FormatterClass()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
