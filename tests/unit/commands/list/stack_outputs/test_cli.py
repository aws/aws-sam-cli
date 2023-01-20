from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.list.stack_outputs.command import do_cli


class TestCli(TestCase):
    def setUp(self):
        self.stack_name = "stack-name"
        self.output = "json"
        self.region = None
        self.profile = None

    @patch("samcli.commands.list.stack_outputs.command.click")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.StackOutputsContext")
    def test_cli_base_command(self, mock_stack_outputs_context, mock_stack_outputs_click):
        context_mock = Mock()
        mock_stack_outputs_context.return_value.__enter__.return_value = context_mock
        do_cli(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
        )

        mock_stack_outputs_context.assert_called_with(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)
