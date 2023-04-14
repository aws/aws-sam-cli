from unittest import TestCase

from samcli.commands.deploy.command import cli
from samcli.commands.deploy.core.options import ALL_OPTIONS


class TestOptions(TestCase):
    def test_all_options_formatted(self):
        command_options = [param.human_readable_name for param in cli.params]
        command_options = [command_option for command_option in command_options if command_option is not None]
        self.assertEqual(sorted(ALL_OPTIONS), sorted(command_options))
