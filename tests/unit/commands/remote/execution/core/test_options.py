from unittest import TestCase

from click import Option

from samcli.commands.remote.execution.get.cli import cli as get_cli
from samcli.commands.remote.execution.history.cli import cli as history_cli
from samcli.commands.remote.execution.stop.cli import cli as stop_cli
from samcli.commands.remote.execution.get.core.options import ALL_OPTIONS as GET_ALL_OPTIONS
from samcli.commands.remote.execution.history.core.options import ALL_OPTIONS as HISTORY_ALL_OPTIONS
from samcli.commands.remote.execution.stop.core.options import ALL_OPTIONS as STOP_ALL_OPTIONS


class TestRemoteExecutionOptions(TestCase):
    def test_get_options_formatted(self):
        command_options = [param.human_readable_name if isinstance(param, Option) else None for param in get_cli.params]
        self.assertEqual(
            sorted(GET_ALL_OPTIONS), sorted(filter(lambda item: item is not None, command_options + ["help"]))
        )

    def test_history_options_formatted(self):
        command_options = [
            param.human_readable_name if isinstance(param, Option) else None for param in history_cli.params
        ]
        self.assertEqual(
            sorted(HISTORY_ALL_OPTIONS), sorted(filter(lambda item: item is not None, command_options + ["help"]))
        )

    def test_stop_options_formatted(self):
        command_options = [
            param.human_readable_name if isinstance(param, Option) else None for param in stop_cli.params
        ]
        self.assertEqual(
            sorted(STOP_ALL_OPTIONS), sorted(filter(lambda item: item is not None, command_options + ["help"]))
        )
