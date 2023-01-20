from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.list.resources.command import do_cli


class TestCli(TestCase):
    def setUp(self):
        self.stack_name = "stack-name"
        self.output = "json"
        self.region = None
        self.profile = None
        self.template_file = None

    @patch("samcli.commands.list.resources.command.click")
    @patch("samcli.commands.list.resources.resources_context.ResourcesContext")
    def test_cli_base_command(self, mock_resources_context, mock_resources_click):
        context_mock = Mock()
        mock_resources_context.return_value.__enter__.return_value = context_mock
        do_cli(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
            template_file=self.template_file,
        )

        mock_resources_context.assert_called_with(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
            template_file=self.template_file,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)
