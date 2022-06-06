from tests.integration.list.resources.resources_integ_base import ResourcesIntegBase
from samcli.commands.list.resources.cli import HELP_TEXT
from tests.testing_utils import run_command


class TestResources(ResourcesIntegBase):
    def test_resources_help_message(self):
        cmdlist = self.get_resources_command_list(help=True)
        command_result = run_command(cmdlist)
        from_command = "".join(command_result.stdout.decode().split())
        from_help = "".join(HELP_TEXT.split())
        self.assertIn(from_help, from_command, "Resources help text should have been printed")
