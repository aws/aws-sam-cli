from unittest import TestCase

from click import Option
from parameterized import parameterized

from samcli.commands.remote.test_event.get.cli import cli as get_cli
from samcli.commands.remote.test_event.list.cli import cli as list_cli
from samcli.commands.remote.test_event.delete.cli import cli as delete_cli
from samcli.commands.remote.test_event.put.cli import cli as put_cli
from samcli.commands.remote.test_event.get.core.options import ALL_OPTIONS as ALL_OPTIONS_GET
from samcli.commands.remote.test_event.list.core.options import ALL_OPTIONS as ALL_OPTIONS_LIST
from samcli.commands.remote.test_event.delete.core.options import ALL_OPTIONS as ALL_OPTIONS_DELETE
from samcli.commands.remote.test_event.put.core.options import ALL_OPTIONS as ALL_OPTIONS_PUT


class TestOptions(TestCase):
    @parameterized.expand(
        [
            (get_cli, ALL_OPTIONS_GET),
            (list_cli, ALL_OPTIONS_LIST),
            (delete_cli, ALL_OPTIONS_DELETE),
            (put_cli, ALL_OPTIONS_PUT),
        ]
    )
    def test_all_options_formatted(self, cli, all_options):
        command_options = [param.human_readable_name if isinstance(param, Option) else None for param in cli.params]
        self.assertEqual(sorted(all_options), sorted(filter(lambda item: item is not None, command_options + ["help"])))
