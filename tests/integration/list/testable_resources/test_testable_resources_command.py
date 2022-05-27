from .testable_resources_integ_base import TestableResourcesIntegBase
from samcli.commands.list.testable_resources.cli import HELP_TEXT
from tests.testing_utils import run_command
import re


class TestTestableResources(TestableResourcesIntegBase):
    def test_testable_resources_help_message(self):
        cmdlist = self.get_testable_resources_command_list(help=True)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        from_command = "".join(re.split("\n*| *", command_result.stdout.decode()))
        from_help = "".join(re.split("\n*| *", HELP_TEXT))
        self.assertTrue(from_help in from_command, "Testable-resources help text should have been printed")
