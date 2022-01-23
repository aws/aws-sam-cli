from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack
from unittest import TestCase
from unittest.mock import patch, call, MagicMock

import click

from samcli.commands.delete.delete_context import DeleteContext
from samcli.lib.package.artifact_exporter import Template
from samcli.cli.cli_config_file import TomlProvider
from samcli.lib.delete.cfn_utils import CfnUtils
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.ecr_uploader import ECRUploader

from samcli.commands.delete.exceptions import CfDeleteFailedStatusError


class TestDeleteContext(TestCase):
    @patch("samcli.commands.delete.delete_context.click.echo")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(return_value=(False)))
    def test_delete_context_stack_does_not_exist(self, patched_click_get_current_context, patched_click_echo):
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            no_prompts=True,
        ) as delete_context:

            delete_context.run()
            expected_click_echo_calls = [
                call(f"Error: The input stack test does" + f" not exist on Cloudformation in the region us-east-1"),
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
            no_prompts=True,
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
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    def test_delete_context_parse_config_file(self, patched_click_get_current_context):
        patched_click_get_current_context = MagicMock()
        with DeleteContext(
            stack_name=None,
            region=None,
            config_file="samconfig.toml",
            config_env="default",
            profile=None,
            no_prompts=True,
        ) as delete_context:
            self.assertEqual(delete_context.stack_name, "test")
            self.assertEqual(delete_context.region, "us-east-1")
            self.assertEqual(delete_context.profile, "developer")
            self.assertEqual(delete_context.s3_bucket, "s3-bucket")
            self.assertEqual(delete_context.s3_prefix, "s3-prefix")

    @patch("samcli.commands.delete.delete_context.prompt")
    @patch("samcli.commands.delete.delete_context.confirm")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(return_value=(False)))
    def test_delete_no_user_input(self, patched_click_get_current_context, patched_confirm, patched_prompt):
        patched_click_get_current_context = MagicMock()
        with DeleteContext(
            stack_name=None,
            region=None,
            config_file=None,
            config_env=None,
            profile=None,
            no_prompts=None,
        ) as delete_context:
            delete_context.run()

            patched_prompt.side_effect = ["sam-app"]
            patched_confirm.side_effect = [True]

            expected_prompt_calls = [
                call(click.style("\tEnter stack name you want to delete", bold=True), type=click.STRING),
            ]

        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

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
    @patch.object(CfnUtils, "has_stack", MagicMock(return_value=(True)))
    @patch.object(CfnUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfnUtils, "delete_stack", MagicMock())
    @patch.object(CfnUtils, "wait_for_delete", MagicMock())
    @patch.object(Template, "get_ecr_repos", MagicMock(return_value=({"logical_id": {"Repository": "test_id"}})))
    @patch.object(S3Uploader, "delete_prefix_artifacts", MagicMock())
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    def test_delete_context_valid_execute_run(self, patched_click_get_current_context):
        patched_click_get_current_context = MagicMock()
        with DeleteContext(
            stack_name=None,
            region=None,
            config_file="samconfig.toml",
            config_env="default",
            profile=None,
            no_prompts=True,
        ) as delete_context:
            delete_context.run()

            self.assertEqual(CfnUtils.has_stack.call_count, 2)
            self.assertEqual(CfnUtils.get_stack_template.call_count, 2)
            self.assertEqual(CfnUtils.delete_stack.call_count, 2)
            self.assertEqual(CfnUtils.wait_for_delete.call_count, 2)
            self.assertEqual(S3Uploader.delete_prefix_artifacts.call_count, 1)
            self.assertEqual(Template.get_ecr_repos.call_count, 2)

    @patch("samcli.commands.delete.delete_context.click.echo")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(side_effect=(True, False)))
    @patch.object(CfnUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfnUtils, "delete_stack", MagicMock())
    @patch.object(CfnUtils, "wait_for_delete", MagicMock())
    def test_delete_context_no_s3_bucket(
        self, patched_click_get_current_context, patched_click_secho, patched_click_echo
    ):
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            no_prompts=True,
        ) as delete_context:

            delete_context.run()
            expected_click_secho_calls = [
                call(
                    "\nWarning: s3_bucket and s3_prefix information could not be obtained from local config file"
                    " or cloudformation template, delete the s3 files manually if required",
                    fg="yellow",
                ),
            ]
            self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

            expected_click_echo_calls = [
                call("\t- Deleting Cloudformation stack test"),
                call("\nDeleted successfully"),
            ]
            self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

    @patch("samcli.commands.delete.delete_context.get_uploaded_s3_object_name")
    @patch("samcli.commands.delete.delete_context.confirm")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(side_effect=(True, False)))
    @patch.object(CfnUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfnUtils, "delete_stack", MagicMock())
    @patch.object(CfnUtils, "wait_for_delete", MagicMock())
    @patch.object(S3Uploader, "delete_artifact", MagicMock())
    def test_guided_prompts_s3_bucket_prefix_present_execute_run(
        self, patched_click_get_current_context, patched_confirm, patched_get_cf_template_name
    ):

        patched_get_cf_template_name.return_value = "hello.template"
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            no_prompts=None,
        ) as delete_context:
            patched_confirm.side_effect = [True, False, True]
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

    @patch("samcli.commands.delete.delete_context.get_uploaded_s3_object_name")
    @patch("samcli.commands.delete.delete_context.confirm")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(side_effect=(True, False)))
    @patch.object(CfnUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfnUtils, "delete_stack", MagicMock())
    @patch.object(CfnUtils, "wait_for_delete", MagicMock())
    @patch.object(S3Uploader, "delete_artifact", MagicMock())
    @patch.object(ECRUploader, "delete_ecr_repository", MagicMock())
    def test_guided_prompts_s3_bucket_present_no_prefix_execute_run(
        self, patched_click_get_current_context, patched_confirm, patched_get_cf_template_name
    ):

        patched_get_cf_template_name.return_value = "hello.template"
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            no_prompts=None,
        ) as delete_context:
            patched_confirm.side_effect = [True, True]
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

    @patch("samcli.commands.delete.delete_context.get_uploaded_s3_object_name")
    @patch("samcli.commands.delete.delete_context.confirm")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(side_effect=(True, True)))
    @patch.object(CfnUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfnUtils, "delete_stack", MagicMock())
    @patch.object(CfnUtils, "wait_for_delete", MagicMock())
    @patch.object(S3Uploader, "delete_artifact", MagicMock())
    @patch.object(ECRUploader, "delete_ecr_repository", MagicMock())
    @patch.object(Template, "get_ecr_repos", MagicMock(side_effect=({}, {"logical_id": {"Repository": "test_id"}})))
    @patch.object(CompanionStack, "stack_name", "Companion-Stack-Name")
    def test_guided_prompts_ecr_companion_stack_present_execute_run(
        self, patched_click_get_current_context, patched_confirm, patched_get_cf_template_name
    ):

        patched_get_cf_template_name.return_value = "hello.template"
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            no_prompts=None,
        ) as delete_context:
            patched_confirm.side_effect = [True, False, True, True, True]
            delete_context.s3_bucket = "s3_bucket"
            delete_context.s3_prefix = "s3_prefix"

            delete_context.run()
            # Now to check for all the defaults on confirmations.
            expected_confirmation_calls = [
                call(
                    click.style(
                        f"\tAre you sure you want to delete the stack test in the region us-east-1 ?",
                        bold=True,
                    ),
                    default=False,
                ),
                call(
                    click.style(
                        "\tAre you sure you want to delete the folder"
                        + " s3_prefix in S3 which contains the artifacts?",
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
                call(
                    click.style(
                        "\tDo you you want to delete the ECR companion stack"
                        + " Companion-Stack-Name in the region us-east-1 ?",
                        bold=True,
                    ),
                    default=False,
                ),
                call(
                    click.style(
                        f"\tECR repository test_id"
                        + " may not be empty. Do you want to delete the repository and all the images in it ?",
                        bold=True,
                    ),
                    default=False,
                ),
            ]

            self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)
            self.assertFalse(delete_context.delete_artifacts_folder)
            self.assertTrue(delete_context.delete_cf_template_file)

    @patch("samcli.commands.delete.delete_context.get_uploaded_s3_object_name")
    @patch("samcli.commands.delete.delete_context.click.echo")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(side_effect=(True, False)))
    @patch.object(CfnUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfnUtils, "delete_stack", MagicMock())
    @patch.object(CfnUtils, "wait_for_delete", MagicMock())
    @patch.object(S3Uploader, "delete_prefix_artifacts", MagicMock())
    @patch.object(ECRUploader, "delete_ecr_repository", MagicMock())
    @patch.object(Template, "get_ecr_repos", MagicMock(return_value=({"logical_id": {"Repository": "test_id"}})))
    @patch.object(CompanionStack, "stack_name", "Companion-Stack-Name")
    def test_no_prompts_input_is_ecr_companion_stack_present_execute_run(
        self, patched_click_get_current_context, patched_click_echo, patched_get_cf_template_name
    ):
        CfnUtils.get_stack_template.return_value = {
            "TemplateBody": {"Metadata": {"CompanionStackname": "Companion-Stack-Name"}}
        }
        patched_get_cf_template_name.return_value = "hello.template"
        with DeleteContext(
            stack_name="Companion-Stack-Name",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            no_prompts=True,
        ) as delete_context:
            delete_context.s3_bucket = "s3_bucket"
            delete_context.s3_prefix = "s3_prefix"

            delete_context.run()
            expected_click_echo_calls = [
                call("\t- Deleting Cloudformation stack Companion-Stack-Name"),
                call("\nDeleted successfully"),
            ]
            self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

    @patch("samcli.commands.delete.delete_context.get_uploaded_s3_object_name")
    @patch("samcli.commands.delete.delete_context.click.get_current_context")
    @patch.object(CfnUtils, "has_stack", MagicMock(side_effect=(True, True)))
    @patch.object(CfnUtils, "get_stack_template", MagicMock(return_value=({"TemplateBody": "Hello World"})))
    @patch.object(CfnUtils, "delete_stack", MagicMock())
    @patch.object(
        CfnUtils,
        "wait_for_delete",
        MagicMock(
            side_effect=(
                CfDeleteFailedStatusError("Companion-Stack-Name", "Mock WaitError"),
                {},
                CfDeleteFailedStatusError("test", "Mock WaitError"),
                {},
            )
        ),
    )
    @patch.object(S3Uploader, "delete_prefix_artifacts", MagicMock())
    @patch.object(ECRUploader, "delete_ecr_repository", MagicMock())
    @patch.object(Template, "get_ecr_repos", MagicMock(side_effect=({}, {"logical_id": {"Repository": "test_id"}})))
    def test_retain_resources_delete_stack(self, patched_click_get_current_context, patched_get_cf_template_name):
        patched_get_cf_template_name.return_value = "hello.template"
        with DeleteContext(
            stack_name="test",
            region="us-east-1",
            config_file="samconfig.toml",
            config_env="default",
            profile="test",
            no_prompts=True,
        ) as delete_context:
            delete_context.s3_bucket = "s3_bucket"
            delete_context.s3_prefix = "s3_prefix"

            delete_context.run()

            self.assertEqual(CfnUtils.has_stack.call_count, 2)
            self.assertEqual(CfnUtils.get_stack_template.call_count, 2)
            self.assertEqual(CfnUtils.delete_stack.call_count, 4)
            self.assertEqual(CfnUtils.wait_for_delete.call_count, 4)
