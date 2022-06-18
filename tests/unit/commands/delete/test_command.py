from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, call, patch

from samcli.commands.delete.command import do_cli
from tests.unit.cli.test_cli_config_file import MockContext


class TestDeleteCliCommand(TestCase):
    def setUp(self):

        self.stack_name = "stack-name"
        self.s3_bucket = "s3-bucket"
        self.s3_prefix = "s3-prefix"
        self.region = None
        self.profile = None
        self.no_prompts = None
        self.config_env = "mock-default-env"
        self.config_file = "mock-default-filename"

    @patch("samcli.commands.delete.command.click")
    @patch("samcli.commands.delete.delete_context.DeleteContext")
    def test_all_args(self, mock_delete_context, mock_delete_click):

        context_mock = Mock()
        mock_delete_context.return_value.__enter__.return_value = context_mock

        do_cli(
            stack_name=self.stack_name,
            region=self.region,
            config_file=self.config_file,
            config_env=self.config_env,
            profile=self.profile,
            no_prompts=self.no_prompts,
            s3_bucket=self.s3_bucket,
            s3_prefix=self.s3_prefix,
        )

        mock_delete_context.assert_called_with(
            stack_name=self.stack_name,
            region=self.region,
            profile=self.profile,
            config_file=self.config_file,
            config_env=self.config_env,
            no_prompts=self.no_prompts,
            s3_bucket=self.s3_bucket,
            s3_prefix=self.s3_prefix,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)
