from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.list.endpoints.cli import do_cli


class TestCli(TestCase):
    def setUp(self):
        self.stack_name = "stack-name"
        self.output = "json"
        self.region = None
        self.profile = None
        self.template_file = None

    @patch("samcli.commands.list.endpoints.cli.click")
    @patch("samcli.commands.list.endpoints.endpoints_context.EndpointsContext")
    def test_cli_base_command(self, mock_endpoints_context, mock_endpoints_click):
        context_mock = Mock()
        mock_endpoints_context.return_value.__enter__.return_value = context_mock
        do_cli(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
            template_file=self.template_file,
        )

        mock_endpoints_context.assert_called_with(
            stack_name=self.stack_name,
            output=self.output,
            region=self.region,
            profile=self.profile,
            template_file=self.template_file,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)
