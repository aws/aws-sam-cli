from tests.integration.list.testable_resources.testable_resources_integ_base import TestableResourcesIntegBase
from samcli.commands.list.testable_resources.cli import HELP_TEXT
from tests.testing_utils import run_command


class TestTestableResources(TestableResourcesIntegBase):
    def test_testable_resources_help_message(self):
        cmdlist = self.get_testable_resources_command_list(help=True)
        command_result = run_command(cmdlist)
        from_command = "".join(command_result.stdout.decode().split())
        from_help = "".join(HELP_TEXT.split())
        self.assertIn(from_help, from_command, "Testable-resources help text should have been printed")
