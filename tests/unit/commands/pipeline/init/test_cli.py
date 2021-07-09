from unittest import TestCase
from unittest.mock import patch

from click.testing import CliRunner

from samcli.commands.pipeline.init.cli import cli as init_cmd
from samcli.commands.pipeline.init.cli import do_cli as init_cli


class TestCli(TestCase):
    @patch("samcli.commands.pipeline.init.cli.do_cli")
    def test_cli_default_flow(self, do_cli_mock):
        runner: CliRunner = CliRunner()
        runner.invoke(init_cmd)
        # Currently we support the interactive mode only, i.e. we don't accept any command arguments,
        # instead we ask the user about the required arguments in an interactive way
        do_cli_mock.assert_called_once_with(False)  # Called without arguments

    @patch("samcli.commands.pipeline.init.cli.InteractiveInitFlow.do_interactive")
    def test_do_cli(self, do_interactive_mock):
        init_cli(False)
        do_interactive_mock.assert_called_once_with()  # Called without arguments
