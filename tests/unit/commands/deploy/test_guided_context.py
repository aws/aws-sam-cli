from unittest import TestCase
from unittest.mock import patch, call, ANY, MagicMock, Mock
from parameterized import parameterized, param

import click

from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.commands.deploy.guided_context import GuidedContext
from samcli.lib.utils.packagetype import ZIP, IMAGE


class TestGuidedContext(TestCase):
    def setUp(self):
        self.image_repository = "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"
        self.gc = GuidedContext(
            template_file="template",
            stack_name="test",
            s3_bucket="s3_b",
            s3_prefix="s3_p",
            confirm_changeset=True,
            region="region",
            image_repository=None,
            image_repositories={"RandomFunction": "image-repo"},
            disable_rollback=False,
        )

        self.unreferenced_repo_mock = MagicMock()

        self.companion_stack_manager_patch = patch("samcli.commands.deploy.guided_context.CompanionStackManager")
        self.companion_stack_manager_mock = self.companion_stack_manager_patch.start()
        self.companion_stack_manager_mock.return_value.set_functions.return_value = None
        self.companion_stack_manager_mock.return_value.get_repository_mapping.return_value = {
            "HelloWorldFunction": self.image_repository
        }
        self.companion_stack_manager_mock.return_value.get_unreferenced_repos.return_value = [
            self.unreferenced_repo_mock
        ]
        self.companion_stack_manager_mock.return_value.get_repo_uri = lambda repo: (
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test2" if repo == self.unreferenced_repo_mock else None
        )

        self.verify_image_patch = patch(
            "samcli.commands.deploy.guided_context.GuidedContext.verify_images_exist_locally"
        )
        self.verify_image_mock = self.verify_image_patch.start()

    def tearDown(self):
        self.companion_stack_manager_patch.stop()
        self.verify_image_patch.stop()

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_defaults_non_public_resources_zips(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patched_auth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        get_resource_full_path_by_id_mock,
    ):
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patched_auth_per_resource.return_value = [
            ("HelloWorldFunction", True),
        ]
        patched_confirm.side_effect = [True, False, False, "", True, True, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
        patched_get_buildable_stacks.assert_called_once_with(
            "template",
            parameter_overrides={},
            global_parameter_overrides={"AWS::Region": ANY},
            language_extensions_enabled=False,
        )

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_defaults_public_resources_zips(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        get_resource_full_path_by_id_mock,
    ):
        patched_signer_config_per_function.return_value = (None, None)
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, False, True, False, True, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.tag_translation")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_defaults_public_resources_images(
        self,
        patched_signer_config_per_function,
        patched_tag_translation,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        get_resource_full_path_by_id_mock,
    ):
        patched_signer_config_per_function.return_value = (None, None)
        patched_tag_translation.return_value = "helloworld-123456-v1"
        function_mock = MagicMock()
        function_mock.packagetype = IMAGE
        function_mock.imageuri = "helloworld:v1"
        function_mock.full_path = "HelloWorldFunction"
        patched_sam_function_provider.return_value.get_all.return_value = [function_mock]
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "CAPABILITY_IAM",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        get_resource_full_path_by_id_mock.return_value = None
        patched_confirm.side_effect = [True, False, False, True, False, True, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Create managed ECR repositories for all functions?{self.gc.end_bold}",
                default=True,
            ),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
        # Now to check click secho outputs
        print(expected_prompt_calls)
        print(patched_prompt.call_args_list)
        expected_click_secho_calls = [
            call("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy"),
            call("\t#SAM needs permission to be able to create roles to connect to the resources in your template"),
            call("\t#Preserves the state of previously provisioned resources when an operation fails"),
            call("\n\tManaged S3 bucket: managed_s3_stack", bold=True),
        ]
        self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_defaults_public_resources_images_ecr_url(
        self,
        patched_signer_config_per_function,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        get_resource_full_path_by_id_mock,
    ):
        function_mock = MagicMock()
        function_mock.packagetype = IMAGE
        function_mock.imageuri = "helloworld:v1"
        function_mock.full_path = "HelloWorldFunction"
        patched_sam_function_provider.return_value.get_all.return_value = [function_mock]
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "CAPABILITY_IAM",
            "abc",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        get_resource_full_path_by_id_mock.return_value = "RandomFunction"
        patched_confirm.side_effect = [True, False, False, True, False, True, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Create managed ECR repositories for all functions?{self.gc.end_bold}",
                default=True,
            ),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
        # Now to check click secho outputs and no references to images pushed.
        expected_click_secho_calls = [
            call("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy"),
            call("\t#SAM needs permission to be able to create roles to connect to the resources in your template"),
            call("\t#Preserves the state of previously provisioned resources when an operation fails"),
            call("\n\tManaged S3 bucket: managed_s3_stack", bold=True),
        ]
        self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_images_illegal_image_uri(
        self,
        patched_signer_config_per_function,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        get_resource_full_path_by_id_mock,
    ):
        function_mock = MagicMock()
        function_mock.packagetype = IMAGE
        function_mock.imageuri = None
        function_mock.full_path = "HelloWorldFunction"
        patched_sam_function_provider.return_value.get_all.return_value = [function_mock]
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "CAPABILITY_IAM",
            "illegaluri",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        get_resource_full_path_by_id_mock.return_value = "RandomFunction"
        patched_confirm.side_effect = [True, False, False, True, False, False, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        with self.assertRaises(GuidedDeployFailedError):
            self.gc.guided_prompts(parameter_override_keys=None)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_images_missing_repo(
        self,
        patched_signer_config_per_function,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        # Set ImageUri to be None, the sam app was never built.
        function_mock_1 = MagicMock()
        function_mock_1.packagetype = IMAGE
        function_mock_1.imageuri = None
        function_mock_1.full_path = "HelloWorldFunction"
        function_mock_2 = MagicMock()
        function_mock_2.packagetype = IMAGE
        function_mock_2.imageuri = None
        function_mock_2.full_path = "RandomFunction"
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_sam_function_provider.return_value.get_all.return_value = [function_mock_1, function_mock_2]
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "CAPABILITY_IAM",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, False, True, False, True, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})

        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Create managed ECR repositories for the 1 functions without?{self.gc.end_bold}",
                default=True,
            ),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
        # Now to check click secho outputs and no references to images pushed.
        expected_click_secho_calls = [
            call("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy"),
            call("\t#SAM needs permission to be able to create roles to connect to the resources in your template"),
            call("\t#Preserves the state of previously provisioned resources when an operation fails"),
            call("\n\tManaged S3 bucket: managed_s3_stack", bold=True),
        ]
        self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_images_no_repo(
        self,
        patched_signer_config_per_function,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        # Set ImageUri to be None, the sam app was never built.
        function_mock = MagicMock()
        function_mock.packagetype = IMAGE
        function_mock.imageuri = None
        function_mock.full_path = "HelloWorldFunction"
        patched_sam_function_provider.return_value.get_all.return_value = [function_mock]
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "CAPABILITY_IAM",
            "123456789012.dkr.ecr.region.amazonaws.com/myrepo",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_confirm.side_effect = [True, False, False, True, False, False, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})

        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Create managed ECR repositories for all functions?{self.gc.end_bold}",
                default=True,
            ),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
            call(
                f"\t {self.gc.start_bold}ECR repository for HelloWorldFunction{self.gc.end_bold}",
                type=click.STRING,
            ),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
        # Now to check click secho outputs and no references to images pushed.
        expected_click_secho_calls = [
            call("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy"),
            call("\t#SAM needs permission to be able to create roles to connect to the resources in your template"),
            call("\t#Preserves the state of previously provisioned resources when an operation fails"),
            call("\n\tManaged S3 bucket: managed_s3_stack", bold=True),
        ]
        self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_images_deny_deletion(
        self,
        patched_signer_config_per_function,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        # Set ImageUri to be None, the sam app was never built.
        function_mock = MagicMock()
        function_mock.packagetype = IMAGE
        function_mock.imageuri = None
        function_mock.full_path = "HelloWorldFunction"
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_sam_function_provider.return_value.get_all.return_value = [function_mock]
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "CAPABILITY_IAM",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, False, True, False, True, False]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        with self.assertRaises(GuidedDeployFailedError):
            self.gc.guided_prompts(parameter_override_keys=None)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_images_blank_image_repository(
        self,
        patched_signer_config_per_function,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        function_mock = MagicMock()
        function_mock.packagetype = IMAGE
        function_mock.imageuri = None
        function_mock.full_path = "HelloWorldFunction"
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_sam_function_provider.return_value.get_all.return_value = [function_mock]
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # set Image repository to be blank.
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "",
            "",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, False, True, False, False, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        with self.assertRaises(GuidedDeployFailedError):
            self.gc.guided_prompts(parameter_override_keys=None)

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
    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_with_given_capabilities(
        self,
        given_capabilities,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        patched_signer_config_per_function.return_value = ({}, {})
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_get_buildable_stacks.return_value = (Mock(), [])
        self.gc.capabilities = given_capabilities
        # Series of inputs to confirmations so that full range of questions are asked.
        patched_confirm.side_effect = [True, False, False, "", True, True, True]
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
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

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_configuration_file_prompt_calls(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_signer_config_per_function.return_value = ({}, {})
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, False, True, True, True, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
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

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_parameter_from_template(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_confirm.side_effect = [True, False, False, True, False, True, True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        parameter_override_from_template = {"MyTestKey": {"Default": "MyTemplateDefaultVal"}}
        self.gc.parameter_overrides_from_cmdline = {}
        self.gc.guided_prompts(parameter_override_keys=parameter_override_from_template)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
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

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_parameter_from_cmd_or_config(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_confirm.side_effect = [True, False, False, True, False, True, True]
        patched_signer_config_per_function.return_value = ({}, {})
        patched_manage_stack.return_value = "managed_s3_stack"
        parameter_override_from_template = {"MyTestKey": {"Default": "MyTemplateDefaultVal"}}
        self.gc.parameter_overrides_from_cmdline = {"MyTestKey": "OverridedValFromCmdLine", "NotUsedKey": "NotUsedVal"}
        self.gc.guided_prompts(parameter_override_keys=parameter_override_from_template)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
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

    @parameterized.expand(
        [
            (False, ({"MyFunction1"}, {})),
            (True, ({"MyFunction1"}, {})),
            (True, ({"MyFunction1", "MyFunction2"}, {})),
            (True, ({"MyFunction1"}, {"MyLayer1": {"MyFunction1"}})),
            (True, ({"MyFunction1"}, {"MyLayer1": {"MyFunction1"}, "MyLayer2": {"MyFunction1"}})),
        ]
    )
    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.code_signer_utils.prompt")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    def test_guided_prompts_with_code_signing(
        self,
        given_sign_packages_flag,
        given_code_signing_configs,
        patched_sam_function_provider,
        patched_signer_config_per_function,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_code_signer_prompt,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
    ):
        # given_sign_packages_flag = True
        # given_code_signing_configs = ({"MyFunction1"}, {"MyLayer1": {"MyFunction1"}, "MyLayer2": {"MyFunction1"}})
        patched_sam_function_provider.return_value.functions = {}
        patched_signer_config_per_function.return_value = given_code_signing_configs
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patched_confirm.side_effect = [True, False, False, given_sign_packages_flag, "", True, True, True]
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}Do you want to sign your code?{self.gc.end_bold}",
                default=True,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        # Now to check for all the defaults on prompts.
        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}", default="region", type=click.STRING),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)

        if given_sign_packages_flag:
            # we are going to expect prompts for functions and layers for each one of them,
            # so multiply the number of prompt calls
            number_of_functions = len(given_code_signing_configs[0])
            number_of_layers = len(given_code_signing_configs[1])
            expected_code_sign_calls = [
                call(f"\t{self.gc.start_bold}Signing Profile Name{self.gc.end_bold}", default=None, type=click.STRING),
                call(
                    f"\t{self.gc.start_bold}Signing Profile Owner Account ID (optional){self.gc.end_bold}",
                    default="",
                    type=click.STRING,
                    show_default=False,
                ),
            ]
            expected_code_sign_calls = expected_code_sign_calls * (number_of_functions + number_of_layers)
            self.assertEqual(expected_code_sign_calls, patched_code_signer_prompt.call_args_list)

    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.get_default_aws_region")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_check_default_config_region(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_default_aws_region,
        patched_get_resource_full_path_by_id,
    ):
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_get_resource_full_path_by_id.return_value = "RandomFunction"
        patched_confirm.side_effect = [True, False, False, True, True, True, True]
        patched_signer_config_per_function.return_value = ({}, {})
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_get_default_aws_region.return_value = "default_config_region"
        # setting the default region to None
        self.gc.region = None
        self.gc.guided_prompts(parameter_override_keys=None)
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Disable rollback{self.gc.end_bold}", default=False),
            call(
                f"\t{self.gc.start_bold}HelloWorldFunction has no authentication. Is this okay?{self.gc.end_bold}",
                default=False,
            ),
            call(f"\t{self.gc.start_bold}Save arguments to configuration file{self.gc.end_bold}", default=True),
            call(
                f"\t {self.gc.start_bold}Delete the unreferenced repositories listed above when deploying?{self.gc.end_bold}",
                default=False,
            ),
        ]
        self.assertEqual(expected_confirmation_calls, patched_confirm.call_args_list)

        expected_prompt_calls = [
            call(f"\t{self.gc.start_bold}Stack Name{self.gc.end_bold}", default="test", type=click.STRING),
            call(
                f"\t{self.gc.start_bold}AWS Region{self.gc.end_bold}",
                default="default_config_region",
                type=click.STRING,
            ),
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

    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.GuidedConfig")
    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_run_saves_config_when_manage_stack_fails(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patched_auth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
        patched_guided_config,
        patched_get_template_parameters,
    ):
        # New project (no existing samconfig): the user answers all the prompts, but manage_stack (the
        # first AWS call requiring credentials) fails, e.g. because of invalid/expired credentials.
        patched_get_template_parameters.return_value = {}
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_auth_per_resource.return_value = [("HelloWorldFunction", True)]
        patched_signer_config_per_function.return_value = ({}, {})
        patched_prompt.side_effect = ["my-stack", "us-west-2", "samconfig.toml", "default"]
        # Confirm changeset, allow IAM, disable rollback, save to config
        patched_confirm.side_effect = [True, True, False, True]

        credentials_error = Exception("The security token included in the request is invalid.")
        patched_manage_stack.side_effect = credentials_error

        guided_config_instance = patched_guided_config.return_value
        # No pre-existing configuration file.
        guided_config_instance.config_exists.return_value = False

        # The original error should still propagate up ...
        with self.assertRaises(Exception) as ctx:
            self.gc.run()
        self.assertIs(ctx.exception, credentials_error)

        # ... but the configuration file must have been saved with the answers already collected.
        guided_config_instance.save_config.assert_called_once()
        _, save_kwargs = guided_config_instance.save_config.call_args
        self.assertEqual(save_kwargs["stack_name"], "my-stack")
        self.assertEqual(save_kwargs["region"], "us-west-2")

    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.GuidedConfig")
    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_run_does_not_overwrite_existing_config_on_failure_by_default(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patched_auth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
        patched_guided_config,
        patched_get_template_parameters,
    ):
        # A samconfig already exists and the user has NOT opted in via --save-params-on-failure.
        # A failure must NOT overwrite the known-good existing configuration.
        patched_get_template_parameters.return_value = {}
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_auth_per_resource.return_value = [("HelloWorldFunction", True)]
        patched_signer_config_per_function.return_value = ({}, {})
        patched_prompt.side_effect = ["my-stack", "us-west-2", "samconfig.toml", "default"]
        patched_confirm.side_effect = [True, True, False, True]

        credentials_error = Exception("The security token included in the request is invalid.")
        patched_manage_stack.side_effect = credentials_error

        guided_config_instance = patched_guided_config.return_value
        # A configuration file already exists.
        guided_config_instance.config_exists.return_value = True

        self.gc.force_save_config = False

        with self.assertRaises(Exception) as ctx:
            self.gc.run()
        self.assertIs(ctx.exception, credentials_error)

        guided_config_instance.save_config.assert_not_called()

    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.GuidedConfig")
    @patch("samcli.commands.deploy.guided_context.get_resource_full_path_by_id")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_run_overwrites_existing_config_on_failure_when_forced(
        self,
        patched_signer_config_per_function,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patched_auth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
        patched_get_resource_full_path_by_id,
        patched_guided_config,
        patched_get_template_parameters,
    ):
        # A samconfig already exists AND the user opted in via --save-params-on-failure.
        # A failure SHOULD save (overwrite) the configuration.
        patched_get_template_parameters.return_value = {}
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_auth_per_resource.return_value = [("HelloWorldFunction", True)]
        patched_signer_config_per_function.return_value = ({}, {})
        patched_prompt.side_effect = ["my-stack", "us-west-2", "samconfig.toml", "default"]
        patched_confirm.side_effect = [True, True, False, True]

        credentials_error = Exception("The security token included in the request is invalid.")
        patched_manage_stack.side_effect = credentials_error

        guided_config_instance = patched_guided_config.return_value
        guided_config_instance.config_exists.return_value = True

        self.gc.force_save_config = True

        with self.assertRaises(Exception) as ctx:
            self.gc.run()
        self.assertIs(ctx.exception, credentials_error)

        guided_config_instance.save_config.assert_called_once()

    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.GuidedConfig")
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    def test_run_does_not_save_config_when_aborted_before_stack_name(
        self,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patched_prompt,
        patched_guided_config,
        patched_get_template_parameters,
    ):
        # The user aborts (Ctrl+C) at the very first prompt, before providing any answers.
        patched_get_template_parameters.return_value = {}
        patched_sam_function_provider.return_value.functions = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = click.exceptions.Abort()

        guided_config_instance = patched_guided_config.return_value

        with self.assertRaises(click.exceptions.Abort):
            self.gc.run()

        # No stack name was collected, so nothing should be saved.
        guided_config_instance.save_config.assert_not_called()
