from unittest import TestCase

from click import Option

from samcli.commands.package.command import cli
from samcli.commands.package.core.options import ALL_OPTIONS


class TestOptions(TestCase):
    def test_all_options_formatted(self):
        command_options = [param.human_readable_name if isinstance(param, Option) else None for param in cli.params]
        self.assertEqual(sorted(ALL_OPTIONS), sorted(filter(lambda item: item is not None, command_options + ["help"])))
