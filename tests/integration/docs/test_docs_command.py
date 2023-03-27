import os

from parameterized import parameterized

from samcli.commands.docs.command_context import SUCCESS_MESSAGE, ERROR_MESSAGE, DocsCommandContext
from samcli.lib.docs.documentation import Documentation, LANDING_PAGE
from tests.integration.docs.docs_integ_base import DocsIntegBase
from tests.testing_utils import run_command

COMMAND_URL_PAIR = [(command, url) for command, url in Documentation.load().items()]


class TestDocsCommand(DocsIntegBase):
    @parameterized.expand(COMMAND_URL_PAIR)
    def test_docs_command(self, command, url):
        sub_commands = command.split(" ")
        command_list = self.get_docs_command_list(sub_commands=sub_commands)
        command_result = run_command(command_list)
        stdout = command_result.stdout.decode("utf-8").strip()
        stderr = command_result.stderr.decode("utf-8").strip()
        self.assertEqual(command_result.process.returncode, 0)
        self._assert_valid_response(stdout, stderr, url)

    def test_base_command(self):
        command_list = self.get_docs_command_list()
        command_result = run_command(command_list)
        stdout = command_result.stdout.decode("utf-8").strip()
        stderr = command_result.stderr.decode("utf-8").strip()
        self.assertEqual(command_result.process.returncode, 0)
        self._assert_valid_response(stdout, stderr, LANDING_PAGE)

    def test_invalid_command(self):
        command_list = self.get_docs_command_list(sub_commands=["wrong", "command"])
        command_result = run_command(command_list)
        stderr = command_result.stderr.decode("utf-8").strip()
        self.assertEqual(command_result.process.returncode, 1)
        self.assertIn(
            f"Error: Command not found. Try using one of the following available commands:",
            stderr,
        )

    def _assert_valid_response(self, stdout, stderr, url):
        # We don't know if the machine this runs on will have a browser,
        # so we're just testing to ensure we get one of two valid command outputs
        return self.assertTrue(SUCCESS_MESSAGE in stdout or ERROR_MESSAGE.format(URL=url) in stderr)
