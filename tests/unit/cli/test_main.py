from unittest import TestCase
from click.testing import CliRunner
from samcli.cli.main import cli


class TestCliBase(TestCase):

    def test_cli_base(self):
        """
        Just invoke the CLI without any commands and assert that help text was printed
        :return:
        """
        runner = CliRunner()
        result = runner.invoke(cli, [])
        self.assertEquals(result.exit_code, 0)
        self.assertTrue("--help" in result.output, "Help text must be printed")
        self.assertTrue("--debug" in result.output, "--debug option must be present in help text")

    def test_cli_some_command(self):

        runner = CliRunner()
        result = runner.invoke(cli, ["local", "generate-event", "s3"])
        self.assertEquals(result.exit_code, 0)

    def test_cli_with_debug(self):

        runner = CliRunner()
        result = runner.invoke(cli, ["local", "generate-event", "s3", "put", "--debug"])
        self.assertEquals(result.exit_code, 0)
