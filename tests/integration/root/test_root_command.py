from parameterized import parameterized

from tests.integration.root.root_integ_base import RootIntegBase
from tests.testing_utils import run_command


class TestRoot(RootIntegBase):
    def test_no_args(self):
        command = self.root_command_list()
        execute_process = run_command(command)
        self.assertEqual(execute_process.process.returncode, 0)

    @parameterized.expand([({"_help": True}, 0), ({"version": True}, 0), ({"info": True}, 0), ({"debug": True}, 2)])
    def test_help(self, arguments, return_code):
        command = self.root_command_list(**arguments)
        execute_process = run_command(command)
        self.assertEqual(execute_process.process.returncode, return_code)
