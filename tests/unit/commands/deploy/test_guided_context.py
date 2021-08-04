from unittest import TestCase
from unittest.mock import patch, call, ANY, MagicMock, Mock
from parameterized import parameterized, param

import click

from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.commands.deploy.guided_context import GuidedContext
from samcli.lib.utils.packagetype import ZIP, IMAGE


class TestGuidedContext(TestCase):
    def setUp(self):
        iac_mock = Mock()
        self.project_mock = project_mock = Mock()
        project_mock.stacks = MagicMock()
        self.gc = GuidedContext(
            stack_name="test",
            s3_bucket="s3_b",
            s3_prefix="s3_p",
            confirm_changeset=True,
            region="region",
            image_repository=None,
            image_repositories={"HelloWorldFunction": "image-repo"},
            iac=iac_mock,
            project=self.project_mock,
        )

    def test_get_iac_stack_stack_name_found(self):
        project_mock = self.gc._project
        project_mock.reset_mock()
        stack_mock = Mock()
        stack_mock.origin_dir = "dir"
        stack_mock.name = "stack_name"
        project_mock.find_stack_by_name.return_value = stack_mock

        self.gc._get_iac_stack("stack_name")
        self.assertEqual(self.gc._iac_stack, stack_mock)
        self.assertEqual(self.gc.template_file, "dir")
        self.assertEqual(self.gc.stack_name, "stack_name")

    def test_get_iac_stack_stack_name_not_found(self):
        project_mock = self.gc._project
        project_mock.reset_mock()
        stack_mock = Mock()
        stack_mock.origin_dir = "dir"
        stack_mock.name = "stack_name"
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = stack_mock

        with self.assertRaises(GuidedDeployFailedError) as ex:
            self.gc._get_iac_stack("test")
        self.assertEqual(
            ex.exception.msg,
            "There is no stack with name 'test'. "
            "If you have specified --stack-name, specify the correct stack name or remove --stack-name to use default.",
        )

    def test_get_iac_stack_stack_name_empty_sting(self):
        project_mock = self.gc._project
        project_mock.reset_mock()
        stack_mock = Mock()
        stack_mock.origin_dir = "dir"
        stack_mock.name = ""
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = stack_mock

        self.gc._get_iac_stack("provided_stack_name")
        self.assertEqual(self.gc._iac_stack, stack_mock)
        self.assertEqual(self.gc.template_file, "dir")
        self.assertEqual(self.gc.stack_name, "provided_stack_name")

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
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [
            ("HelloWorldFunction", True),
        ]
        patched_confirm.side_effect = [True, False, "", True]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        self.gc.guided_prompts()
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
        patched_get_buildable_stacks.assert_called_once_with(
            "template", parameter_overrides={}, global_parameter_overrides={"AWS::Region": ANY}
        )

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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_signer_config_per_function.return_value = (None, None)
        patched_sam_function_provider.return_value = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts()
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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = True
        function_resource_mock = Mock()
        function_resource_mock.item_id = "HelloWorldFunction"
        iac_stack_mock.find_function_resources_of_package_type.return_value = [function_resource_mock]
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_signer_config_per_function.return_value = (None, None)
        patched_tag_translation.return_value = "helloworld-123456-v1"
        patched_sam_function_provider.return_value = MagicMock(
            functions={"HelloWorldFunction": MagicMock(packagetype=IMAGE, imageuri="helloworld:v1")}
        )
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "123456789012.dkr.ecr.region.amazonaws.com/myrepo",
            "CAPABILITY_IAM",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts()
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
            call(
                f"\t{self.gc.start_bold}Image Repository for HelloWorldFunction{self.gc.end_bold}",
                default="image-repo",
            ),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
        # Now to check click secho outputs
        print(expected_prompt_calls)
        print(patched_prompt.call_args_list)
        expected_click_secho_calls = [
            call(
                f"\t  helloworld:v1 to be pushed to 123456789012.dkr.ecr.region.amazonaws.com/myrepo:helloworld-123456-v1"
            ),
            call(nl=True),
            call("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy"),
            call("\t#SAM needs permission to be able to create roles to connect to the resources in your template"),
        ]
        self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = True
        function_resource_mock = Mock()
        function_resource_mock.item_id = "HelloWorldFunction"
        iac_stack_mock.find_function_resources_of_package_type.return_value = [function_resource_mock]
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = MagicMock(
            functions={
                "HelloWorldFunction": MagicMock(
                    packagetype=IMAGE, imageuri="123456789012.dkr.ecr.region.amazonaws.com/myrepo"
                )
            }
        )
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "123456789012.dkr.ecr.region.amazonaws.com/myrepo",
            "CAPABILITY_IAM",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        self.gc.guided_prompts()
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
            call(
                f"\t{self.gc.start_bold}Image Repository for HelloWorldFunction{self.gc.end_bold}",
                default="image-repo",
            ),
            call(f"\t{self.gc.start_bold}Capabilities{self.gc.end_bold}", default=["CAPABILITY_IAM"], type=ANY),
        ]
        self.assertEqual(expected_prompt_calls, patched_prompt.call_args_list)
        # Now to check click secho outputs and no references to images pushed.
        expected_click_secho_calls = [
            call(nl=True),
            call("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy"),
            call("\t#SAM needs permission to be able to create roles to connect to the resources in your template"),
        ]
        self.assertEqual(expected_click_secho_calls, patched_click_secho.call_args_list)

    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.deploy.guided_context.SamFunctionProvider")
    @patch("samcli.commands.deploy.guided_context.click.secho")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    def test_guided_prompts_images_no_image_uri(
        self,
        patched_signer_config_per_function,
        patched_click_secho,
        patched_sam_function_provider,
        patched_get_buildable_stacks,
        patchedauth_per_resource,
        patched_manage_stack,
        patched_confirm,
        patched_prompt,
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = True
        function_resource_mock = Mock()
        function_resource_mock.item_id = "HelloWorldFunction"
        iac_stack_mock.find_function_resources_of_package_type.return_value = [function_resource_mock]
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        # Set ImageUri to be None, the sam app was never built.
        patched_sam_function_provider.return_value = MagicMock(
            functions={"HelloWorldFunction": MagicMock(packagetype=IMAGE, imageuri=None)}
        )
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "123456789012.dkr.ecr.region.amazonaws.com/myrepo",
            "CAPABILITY_IAM",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        with self.assertRaises(GuidedDeployFailedError):
            self.gc.guided_prompts()

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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = True
        function_resource_mock = Mock()
        function_resource_mock.item_id = "HelloWorldFunction"
        iac_stack_mock.find_function_resources_of_package_type.return_value = [function_resource_mock]
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = MagicMock(
            functions={"HelloWorldFunction": MagicMock(packagetype=IMAGE, imageuri="mysamapp:v1")}
        )
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # set Image repository to be blank.
        patched_prompt.side_effect = [
            "sam-app",
            "region",
            "",
        ]
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        with self.assertRaises(GuidedDeployFailedError):
            self.gc.guided_prompts()

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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_signer_config_per_function.return_value = ({}, {})
        patched_get_buildable_stacks.return_value = (Mock(), [])
        self.gc.capabilities = given_capabilities
        # Series of inputs to confirmations so that full range of questions are asked.
        patched_confirm.side_effect = [True, False, "", True]
        self.gc.guided_prompts()
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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        patched_signer_config_per_function.return_value = ({}, {})
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, True, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.guided_prompts()
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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {"MyTestKey": {"Default": "MyTemplateDefaultVal"}}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_signer_config_per_function.return_value = ({}, {})
        self.gc.parameter_overrides_from_cmdline = {}
        self.gc.guided_prompts()
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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {"MyTestKey": {"Default": "MyTemplateDefaultVal"}}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, False, ""]
        patched_signer_config_per_function.return_value = ({}, {})
        patched_manage_stack.return_value = "managed_s3_stack"
        self.gc.parameter_overrides_from_cmdline = {"MyTestKey": "OverridedValFromCmdLine", "NotUsedKey": "NotUsedVal"}
        self.gc.guided_prompts()
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

    @parameterized.expand(
        [
            (False, ({"MyFunction1"}, {})),
            (True, ({"MyFunction1"}, {})),
            (True, ({"MyFunction1", "MyFunction2"}, {})),
            (True, ({"MyFunction1"}, {"MyLayer1": {"MyFunction1"}})),
            (True, ({"MyFunction1"}, {"MyLayer1": {"MyFunction1"}, "MyLayer2": {"MyFunction1"}})),
        ]
    )
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
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = {}
        patched_signer_config_per_function.return_value = given_code_signing_configs
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patched_confirm.side_effect = [True, False, given_sign_packages_flag, "", True]
        self.gc.guided_prompts()
        # Now to check for all the defaults on confirmations.
        expected_confirmation_calls = [
            call(f"\t{self.gc.start_bold}Confirm changes before deploy{self.gc.end_bold}", default=True),
            call(f"\t{self.gc.start_bold}Allow SAM CLI IAM role creation{self.gc.end_bold}", default=True),
            call(
                f"\t{self.gc.start_bold}Do you want to sign your code?{self.gc.end_bold}",
                default=True,
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

    @patch("samcli.commands.deploy.guided_context.get_session")
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
        patched_get_session,
    ):
        project_mock = self.gc._project
        project_mock.reset_mock()
        iac_stack_mock = MagicMock()
        iac_stack_mock.origin_dir = "dir"
        iac_stack_mock.name = ""
        iac_stack_mock.has_assets_of_package_type.return_value = False
        iac_stack_mock.get_overrideable_parameters.return_value = {}
        project_mock.find_stack_by_name.return_value = None
        project_mock.default_stack = iac_stack_mock

        patched_sam_function_provider.return_value = {}
        patched_get_buildable_stacks.return_value = (Mock(), [])
        # Series of inputs to confirmations so that full range of questions are asked.
        patchedauth_per_resource.return_value = [("HelloWorldFunction", False)]
        patched_confirm.side_effect = [True, False, True, True, ""]
        patched_signer_config_per_function.return_value = ({}, {})
        patched_manage_stack.return_value = "managed_s3_stack"
        patched_get_session.return_value.get_config_variable.return_value = "default_config_region"
        # setting the default region to None
        self.gc.region = None
        self.gc.guided_prompts()
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
