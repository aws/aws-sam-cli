from .resources_integ_base import ResourcesIntegBase
from samcli.commands.list.resources.cli import HELP_TEXT
from tests.testing_utils import run_command
import re


class TestResources(ResourcesIntegBase):
    def test_resources_help_message(self):
        cmdlist = self.get_resources_command_list(help=True)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        from_command = "".join(re.split(" *", str(command_result.stdout).replace("\\n", "")))
        from_help = "".join(re.split("\n*| *", HELP_TEXT))
        self.assertTrue(from_help in from_command, "Resources help text should have been printed")


