from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.list.testable_resources.cli import do_cli


class TestCli(TestCase):
    def setUp(self):
        self.stack_name = "stack-name"
        self.output = "json"
        self.region = None
        self.profile = None

    @patch("samcli.commands.list.testable_resources.cli.click")
    def test_cli_base_command(self, mock_testable_resources_click):
        context_mock = Mock()
        do_cli(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
        )
