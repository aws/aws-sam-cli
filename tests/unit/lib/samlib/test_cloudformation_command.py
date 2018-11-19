"""
Tests Deploy  CLI
"""

from subprocess import CalledProcessError

from unittest import TestCase
from mock import patch

from samcli.lib.samlib.cloudformation_command import execute_command


class TestCli(TestCase):

    def setUp(self):
        self.args = ("--arg1", "value1", "different args", "more")

    @patch("subprocess.check_call")
    @patch("platform.system")
    def test_must_add_template_file(self, platform_system_mock, check_call_mock):
        platform_system_mock.return_value = "Linux"
        check_call_mock.return_value = True
        execute_command("command", self.args, "/path/to/template")

        check_call_mock.assert_called_with(["aws", "cloudformation", "command"] +
                                           ["--arg1", "value1", "different args", "more",
                                            "--template-file", "/path/to/template"])

    @patch("subprocess.check_call")
    @patch("platform.system")
    def test_command_must_call_aws_linux(self, platform_system_mock, check_call_mock):
        platform_system_mock.return_value = "Linux"
        check_call_mock.return_value = True
        execute_command("command", self.args, None)
        check_call_mock.assert_called_with(["aws", "cloudformation", "command"] + list(self.args))

    @patch("subprocess.check_call")
    @patch("platform.system")
    def test_command_must_call_aws_windows(self, platform_system_mock, check_call_mock):
        platform_system_mock.return_value = "Windows"
        check_call_mock.return_value = True
        execute_command("command", self.args, None)
        check_call_mock.assert_called_with(["aws.cmd", "cloudformation", "command"] + list(self.args))

    @patch("sys.exit")
    @patch("subprocess.check_call")
    @patch("platform.system")
    def test_command_must_exit_with_status_code(self, platform_system_mock, check_call_mock, exit_mock):
        platform_system_mock.return_value = "Any"
        check_call_mock.side_effect = CalledProcessError(2, "Error")
        exit_mock.return_value = True
        execute_command("command", self.args, None)
        exit_mock.assert_called_with(2)
