from unittest import TestCase
from unittest.mock import patch, call, MagicMock

import click

from samcli.commands.delete.delete_context import DeleteContext
from samcli.cli.cli_config_file import TomlProvider


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
