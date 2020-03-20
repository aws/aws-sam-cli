from unittest import TestCase
from unittest.mock import patch, call, ANY

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
    def test_guided_prompts_check_defaults(self, patched_manage_stack, patched_confirm, patched_prompt):
        # Series of inputs to confirmations so that full range of questions are asked.
        patched_confirm.side_effect = [True, False, "", True]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Save arguments to samconfig.toml{self.gc.end_bold}", default=True),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
