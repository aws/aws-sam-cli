from unittest import TestCase
from unittest.mock import patch


class TestCli(TestCase):
    def setUp(self):
        self.stack_name = "stack-name"
        self.output = "json"

    @patch("samcli.commands.list.resources.cli.click")
    def test_cli_base_command(self, mock_resources_context):
        pass
