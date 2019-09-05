"""
Tests Deploy CLI command
"""

from unittest import TestCase
from mock import patch

from samcli.commands.deploy import do_cli as deploy_cli


class TestCli(TestCase):
    def setUp(self):
        self.args = ("--force-upload",)
        self.expected_args = self.args + ("--stack-name", "stackName")

    @patch("samcli.commands.deploy.execute_command")
    def test_deploy_must_pass_args(self, execute_command_mock):
        execute_command_mock.return_value = True
        deploy_cli(self.args, "file.yaml", "stackName")
        execute_command_mock.assert_called_with("deploy", self.expected_args, template_file="file.yaml")
