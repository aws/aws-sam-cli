from samcli.commands.docs.docs_context import DocsContext
from tests.integration.docs.docs_integ_base import DocsIntegBase
from tests.testing_utils import run_command


class TestDocsCommand(DocsIntegBase):
    def test_docs_command(self):
        command_list = self.get_docs_command_list()
        command_result = run_command(command_list)
        stdout = command_result.stdout.decode("utf-8").strip()
        expected_message = (
            f"Opening documentation in the browser. "
            f"If the page fails to open, use the following link: {DocsContext.URL}"
        )
        self.assertEqual(command_result.process.returncode, 0)
        self.assertIn(expected_message, stdout)
