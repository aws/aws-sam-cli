from samcli.commands.docs.docs_context import DocsContext, SUCCESS_MESSAGE, ERROR_MESSAGE
from tests.integration.docs.docs_integ_base import DocsIntegBase
from tests.testing_utils import run_command, RUNNING_ON_CI


class TestDocsCommand(DocsIntegBase):
    def test_docs_command(self):
        command_list = self.get_docs_command_list()
        command_result = run_command(command_list)
        stdout = command_result.stdout.decode("utf-8").strip()
        self.assertEqual(command_result.process.returncode, 0)
        self._assert_valid_response(stdout)

    def _assert_valid_response(self, stdout):
        # We don't know if the machine this runs on will have a browser,
        # so we're just testing to ensure we get one of two valid command outputs
        return self.assertTrue(SUCCESS_MESSAGE in stdout or ERROR_MESSAGE.format(URL=DocsContext.URL) in stdout)
