from unittest import TestCase
from unittest.mock import patch, call, MagicMock

import click

from samcli.commands.delete.delete_context import DeleteContext
from samcli.cli.cli_config_file import TomlProvider
from samcli.lib.delete.cf_utils import CfUtils
from samcli.lib.package.s3_uploader import S3Uploader


class TestDeleteContext(TestCase):
    @patch("samcli.commands.delete.delete_context.click.echo")
    @patch.object(CfUtils, "has_stack", MagicMock(return_value=(False)))
    def test_delete_context_stack_does_not_exist(self, patched_click_echo):
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            force=True,
        ) as delete_context:

            delete_context.run()
            expected_click_echo_calls = [
                call(f"Error: The input stack test does not exist on Cloudformation"),
            ]
            self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

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
    @patch("samcli.commands.deploy.guided_context.click.get_current_context")
    def test_delete_context_parse_config_file(self, patched_click_get_current_context):
        patched_click_get_current_context = MagicMock()
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
    @patch("samcli.commands.deploy.guided_context.click.get_current_context")
    def test_delete_context_valid_execute_run(self, patched_click_get_current_context):
        patched_click_get_current_context = MagicMock()
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

    @patch("samcli.commands.delete.delete_context.click.echo")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch.object(CfUtils, "has_stack", MagicMock(return_value=(True)))
    @patch.object(CfUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfUtils, "delete_stack", MagicMock())
    @patch.object(CfUtils, "wait_for_delete", MagicMock())
    def test_delete_context_no_s3_bucket(self, patched_click_secho, patched_click_echo):
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            force=True,
        ) as delete_context:

            delete_context.run()
            expected_click_secho_calls = [
                call(
                    "\nWarning: s3_bucket and s3_prefix information cannot be obtained,"
                    " delete the files manually if required",
                    fg="yellow",
                ),
            ]
            self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

            expected_click_echo_calls = [
                call("\n\t- Deleting Cloudformation stack test"),
                call("\nDeleted successfully"),
            ]
            self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

    @patch("samcli.commands.delete.delete_context.get_cf_template_name")
    @patch("samcli.commands.delete.delete_context.confirm")
    @patch.object(CfUtils, "has_stack", MagicMock(return_value=(True)))
    @patch.object(CfUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfUtils, "delete_stack", MagicMock())
    @patch.object(CfUtils, "wait_for_delete", MagicMock())
    @patch.object(S3Uploader, "delete_artifact", MagicMock())
    def test_guided_prompts_s3_bucket_prefix_present_execute_run(self, patched_confirm, patched_get_cf_template_name):

        patched_get_cf_template_name.return_value = "hello.template"
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            force=None,
        ) as delete_context:
            patched_confirm.side_effect = [True, False, True]
            delete_context.cf_template_file_name = "hello.template"
            delete_context.s3_bucket = "s3_bucket"
            delete_context.s3_prefix = "s3_prefix"

            delete_context.run()
            # Now to check for all the defaults on confirmations.
            expected_confirmation_calls = [
                call(
                    click.style(
                        f"\tAre you sure you want to delete the stack test" + f" in the region us-east-1 ?",
                        bold=True,
                    ),
                    default=False,
                ),
                call(
                    click.style(
                        "\tAre you sure you want to delete the folder"
                        + f" s3_prefix in S3 which contains the artifacts?",
                        bold=True,
                    ),
                    default=False,
                ),
                call(
                    click.style(
                        "\tDo you want to delete the template file hello.template in S3?",
                        bold=True,
                    ),
                    default=False,
                ),
            ]

            self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)
            self.assertFalse(delete_context.delete_artifacts_folder)
            self.assertTrue(delete_context.delete_cf_template_file)

    @patch("samcli.commands.delete.delete_context.get_cf_template_name")
    @patch("samcli.commands.delete.delete_context.confirm")
    @patch.object(CfUtils, "has_stack", MagicMock(return_value=(True)))
    @patch.object(CfUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfUtils, "delete_stack", MagicMock())
    @patch.object(CfUtils, "wait_for_delete", MagicMock())
    @patch.object(S3Uploader, "delete_artifact", MagicMock())
    def test_guided_prompts_s3_bucket_present_no_prefix_execute_run(
        self, patched_confirm, patched_get_cf_template_name
    ):

        patched_get_cf_template_name.return_value = "hello.template"
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            force=None,
        ) as delete_context:
            patched_confirm.side_effect = [True, True]
            delete_context.cf_template_file_name = "hello.template"
            delete_context.s3_bucket = "s3_bucket"

            delete_context.run()
            # Now to check for all the defaults on confirmations.
            expected_confirmation_calls = [
                call(
                    click.style(
                        f"\tAre you sure you want to delete the stack test" + f" in the region us-east-1 ?",
                        bold=True,
                    ),
                    default=False,
                ),
                call(
                    click.style(
                        "\tDo you want to delete the template file hello.template in S3?",
                        bold=True,
                    ),
                    default=False,
                ),
            ]

            self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)
            self.assertTrue(delete_context.delete_cf_template_file)
