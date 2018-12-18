"""
Tests Package CLI command
"""

from unittest import TestCase
from mock import patch

from samcli.commands.package import do_cli as package_cli


class TestCli(TestCase):

    def setUp(self):
        self.args = ("--template-file", "file.yaml", "--s3-bucket", "bucketName")

    @patch("samcli.commands.package.execute_command")
    def test_package_must_pass_args(self, execute_command_mock):
        execute_command_mock.return_value = True
        package_cli(self.args, "template_file")
        execute_command_mock.assert_called_with("package", self.args, "template_file")
