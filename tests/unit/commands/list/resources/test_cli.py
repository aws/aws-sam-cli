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

    @patch("samcli.commands.list.resources.command.stack_name_not_provided_message")
    @patch("samcli.commands.list.resources.command.click")
    @patch("samcli.commands.list.resources.resources_context.ResourcesContext")
    def test_cli_base_command(self, mock_resources_context, mock_resources_click, mock_stack_name_not_provided):
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
        mock_stack_name_not_provided.assert_not_called()

    @patch("samcli.commands.list.resources.command.stack_name_not_provided_message")
    @patch("samcli.commands.list.resources.command.click")
    @patch("samcli.commands.list.resources.resources_context.ResourcesContext")
    def test_warns_user_stack_name_not_provided(
        self, mock_resources_context, mock_resources_click, mock_stack_name_not_provided
    ):
        do_cli(
            stack_name=None,
            output=self.output,
            region=self.region,
            profile=self.profile,
            template_file=self.template_file,
        )
        mock_stack_name_not_provided.assert_called_once()
