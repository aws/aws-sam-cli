from unittest import TestCase
from unittest.mock import patch, call, ANY
from parameterized import parameterized, param

import click

from samcli.commands.deploy.guided_context import GuidedContext


class TestGuidedContext(TestCase):
    def setUp(self):
        self.gc = GuidedContext(
            template_file="template",
            stack_name="test",
            s3_bucket="s3_b",
            s3_prefix="s3_p",
            confirm_changeset=True,
            region="region",
        )

    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    def test_guided_prompts_check_defaults_non_public_resources(
        self, patched_get_template_data, patchedauth_per_resource, patched_manage_stack, patched_confirm, patched_prompt
    ):
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [
            ("HelloWorldFunction", True),
        ]
        patched_confirm.side_effect = [True, False, "", True]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    def test_guided_prompts_check_defaults_public_resources(
        self, patched_get_template_data, patchedauth_per_resource, patched_manage_stack, patched_confirm, patched_prompt
    ):
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction may not have authorization defined, Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

    @parameterized.expand(
        [
            param((("CAPABILITY_IAM",),)),
            param((("CAPABILITY_AUTO_EXPAND",),)),
            param(
                (
                    (
                        "CAPABILITY_AUTO_EXPAND",
                        "CAPABILITY_IAM",
                    ),
                )
            ),
        ]
    )
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    def test_guided_prompts_with_given_capabilities(
        self,
        given_capabilities,
        patched_get_template_data,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
    ):
        self.gc.capabilities = given_capabilities
        # Series of inputs to confirmations so that full range of questions are asked.
        patched_confirm.side_effect = [True, False, "", True]
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_capabilities = list(given_capabilities[0])
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=expected_capabilities, type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    def test_guided_prompts_check_configuration_file_prompt_calls(
        self, patched_get_template_data, patchedauth_per_resource, patched_manage_stack, patched_confirm, patched_prompt
    ):
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, True, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction may not have authorization defined, Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
            call(
                f"\t{self.gc.start_bold}SAM configuration file{self.gc.end_bold}",
                default="samconfig.toml",
                type=click.STRING,
            ),
            call(
                f"\t{self.gc.start_bold}SAM configuration environment{self.gc.end_bold}",
                default="default",
                type=click.STRING,
            ),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    def test_guided_prompts_check_parameter_from_template(
        self, patched_get_template_data, patchedauth_per_resource, patched_manage_stack, patched_confirm, patched_prompt
    ):
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        parameter_override_from_template = {"MyTestKey": {"Default": "MyTemplateDefaultVal"}}
        self.gc.parameter_overrides_from_cmdline = {}
        self.gc.guided_prompts(parameter_override_keys=parameter_override_from_template)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction may not have authorization defined, Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(
                f"\t{self.gc.start_bold}Parameter MyTestKey{self.gc.end_bold}",
                default="MyTemplateDefaultVal",
                type=click.STRING,
            ),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    def test_guided_prompts_check_parameter_from_cmd_or_config(
        self, patched_get_template_data, patchedauth_per_resource, patched_manage_stack, patched_confirm, patched_prompt
    ):
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        parameter_override_from_template = {"MyTestKey": {"Default": "MyTemplateDefaultVal"}}
        self.gc.parameter_overrides_from_cmdline = {"MyTestKey": "OverridedValFromCmdLine", "NotUsedKey": "NotUsedVal"}
        self.gc.guided_prompts(parameter_override_keys=parameter_override_from_template)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction may not have authorization defined, Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(
                f"\t{self.gc.start_bold}Parameter MyTestKey{self.gc.end_bold}",
                default="OverridedValFromCmdLine",
                type=click.STRING,
            ),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
