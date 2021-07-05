from unittest import TestCase
from unittest.mock import patch, call, MagicMock

import click

from samcli.commands.delete.delete_context import DeleteContext
from samcli.cli.cli_config_file import TomlProvider
from samcli.lib.delete.cf_utils import CfUtils
from samcli.lib.package.s3_uploader import S3Uploader

class TestDeleteContext(TestCase):
    @patch.object(DeleteContext, "parse_config_file", MagicMock())
    @patch.object(DeleteContext, "init_clients", MagicMock())
    def test_delete_context_enter(self):
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            force=True,
        ) as delete_context:
            self.assertEqual(delete_context.parse_config_file.call_count, 1)
            self.assertEqual(delete_context.init_clients.call_count, 1)

    @patch.object(
        TomlProvider,
        "__call__",
        MagicMock(
            return_value=(
                {
                    "stack_name": "test",
                    "region": "us-east-1",
                    "profile": "developer",
                    "s3_bucket": "s3-bucket",
                    "s3_prefix": "s3-prefix",
                }
            )
        ),
    )
    def test_delete_context_parse_config_file(self):
        with DeleteContext(
            stack_name=None,
            region=None,
            config_file="samconfig.toml",
            config_env="default",
            profile=None,
            force=True,
        ) as delete_context:
            self.assertEqual(delete_context.stack_name, "test")
            self.assertEqual(delete_context.region, "us-east-1")
            self.assertEqual(delete_context.profile, "developer")
            self.assertEqual(delete_context.s3_bucket, "s3-bucket")
            self.assertEqual(delete_context.s3_prefix, "s3-prefix")

    @patch.object(
        TomlProvider,
        "__call__",
        MagicMock(
            return_value=(
                {
                    "stack_name": "test",
                    "region": "us-east-1",
                    "profile": "developer",
                    "s3_bucket": "s3-bucket",
                    "s3_prefix": "s3-prefix",
                }
            )
        ),
    )
    @patch.object(CfUtils, "has_stack", MagicMock(return_value=(True)))
    @patch.object(CfUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfUtils, "delete_stack", MagicMock())
    @patch.object(CfUtils, "wait_for_delete", MagicMock())
    @patch.object(S3Uploader, "delete_prefix_artifacts", MagicMock())
    def test_delete_context_valid_execute_run(self):
        with DeleteContext(
            stack_name=None,
            region=None,
            config_file="samconfig.toml",
            config_env="default",
            profile=None,
            force=True,
        ) as delete_context:
            delete_context.run()

            self.assertEqual(CfUtils.has_stack.call_count, 1)
            self.assertEqual(CfUtils.get_stack_template.call_count, 1)
            self.assertEqual(CfUtils.delete_stack.call_count, 1)
            self.assertEqual(CfUtils.wait_for_delete.call_count, 1)
            self.assertEqual(S3Uploader.delete_prefix_artifacts.call_count, 1)
