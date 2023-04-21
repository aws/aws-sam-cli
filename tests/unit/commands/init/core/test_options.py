from unittest import TestCase

from samcli.commands.init.command import cli
from samcli.commands.init.core.options import ALL_OPTIONS


class TestOptions(TestCase):
    def test_all_options_formatted(self):
        command_options = [param.human_readable_name for param in cli.params]
        command_options = [command_option for command_option in command_options if command_option is not None]
        # NOTE: "--help" is a special flag added by click by default, thus not exist in cli.params
        self.assertEqual(set(ALL_OPTIONS) - set(("help",)), set(command_options))
