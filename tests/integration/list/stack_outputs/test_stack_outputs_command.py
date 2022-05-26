from .stack_outputs_integ_base import StackOutputsIntegBase
from samcli.commands.list.stack_outputs.cli import HELP_TEXT
from tests.testing_utils import run_command
import re

class TestStackOutputs(StackOutputsIntegBase):
    def test_stack_outputs_help_message(self):
        cmdlist = self.get_stack_outputs_command_list(help=True)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        from_command = "".join(re.split(" *", str(command_result.stdout).replace("\\n", "")))
        from_help = "".join(re.split("\n*| *", HELP_TEXT))
        self.assertTrue(from_help in from_command, "Stack-outputs help text should have been printed")


