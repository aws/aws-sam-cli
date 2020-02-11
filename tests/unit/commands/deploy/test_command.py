from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, call, patch

from samcli.commands.deploy.command import do_cli
from samcli.commands.deploy.guided_config import GuidedConfig
from tests.unit.cli.test_cli_config_file import MockContext


def get_mock_sam_config():
    mock_sam_config = MagicMock()
    mock_sam_config.exists = MagicMock(return_value=True)
    return mock_sam_config


MOCK_SAM_CONFIG = get_mock_sam_config()


class TestDeployCliCommand(TestCase):
    def setUp(self):

        self.template_file = "input-template-file"
        self.stack_name = "stack-name"
        self.s3_bucket = "s3-bucket"
        self.s3_prefix = "s3-prefix"
        self.kms_key_id = "kms-key-id"
        self.no_execute_changeset = False
        self.notification_arns = []
        self.parameter_overrides = {"a": "b"}
        self.capabilities = ("CAPABILITY_IAM",)
        self.tags = {"c": "d"}
        self.fail_on_empty_changset = True
        self.role_arn = "role_arn"
        self.force_upload = False
        self.metadata = {"abc": "def"}
        self.region = None
        self.profile = None
        self.use_json = True
        self.metadata = {}
        self.guided = False
        self.confirm_changeset = False
        MOCK_SAM_CONFIG.reset_mock()

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    def test_all_args(self, mock_deploy_context, mock_deploy_click, mock_package_context, mock_package_click):

        context_mock = Mock()
        mock_deploy_context.return_value.__enter__.return_value = context_mock

        do_cli(
            template_file=self.template_file,
            stack_name=self.stack_name,
            s3_bucket=self.s3_bucket,
            force_upload=self.force_upload,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            no_execute_changeset=self.no_execute_changeset,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            fail_on_empty_changeset=self.fail_on_empty_changset,
            tags=self.tags,
            region=self.region,
            profile=self.profile,
            use_json=self.use_json,
            metadata=self.metadata,
            guided=self.guided,
            confirm_changeset=self.confirm_changeset,
        )

        mock_deploy_context.assert_called_with(
            template_file=ANY,
            stack_name=self.stack_name,
            s3_bucket=self.s3_bucket,
            force_upload=self.force_upload,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            no_execute_changeset=self.no_execute_changeset,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            fail_on_empty_changeset=self.fail_on_empty_changset,
            tags=self.tags,
            region=self.region,
            profile=self.profile,
            confirm_changeset=self.confirm_changeset,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.command.print_deploy_args")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch.object(GuidedConfig, "get_config_ctx", MagicMock(return_value=(None, get_mock_sam_config())))
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    def test_all_args_guided(
        self,
        mock_confirm,
        mock_prompt,
        mock_get_template_parameters,
        mock_managed_stack,
        mock_print_deploy_args,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):

        context_mock = Mock()
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_confirm.side_effect = [True, False, True]
        mock_prompt.side_effect = ["sam-app", "us-west-2", "guidedParameter", "secure", ("CAPABILITY_IAM",)]

        mock_get_template_parameters.return_value = {
            "Myparameter": {"Type": "String"},
            "MyNoEchoParameter": {"Type": "String", "NoEcho": True},
        }

        mock_managed_stack.return_value = "managed-s3-bucket"

        with patch.object(GuidedConfig, "save_config", MagicMock(return_value=True)) as mock_save_config:
            do_cli(
                template_file=self.template_file,
                stack_name=self.stack_name,
                s3_bucket=None,
                force_upload=self.force_upload,
                s3_prefix=self.s3_prefix,
                kms_key_id=self.kms_key_id,
                parameter_overrides=self.parameter_overrides,
                capabilities=self.capabilities,
                no_execute_changeset=self.no_execute_changeset,
                role_arn=self.role_arn,
                notification_arns=self.notification_arns,
                fail_on_empty_changeset=self.fail_on_empty_changset,
                tags=self.tags,
                region=self.region,
                profile=self.profile,
                use_json=self.use_json,
                metadata=self.metadata,
                guided=True,
                confirm_changeset=True,
            )

            mock_deploy_context.assert_called_with(
                template_file=ANY,
                stack_name="sam-app",
                s3_bucket="managed-s3-bucket",
                force_upload=self.force_upload,
                s3_prefix="sam-app",
                kms_key_id=self.kms_key_id,
                parameter_overrides={"Myparameter": "guidedParameter", "MyNoEchoParameter": "secure"},
                capabilities=self.capabilities,
                no_execute_changeset=self.no_execute_changeset,
                role_arn=self.role_arn,
                notification_arns=self.notification_arns,
                fail_on_empty_changeset=self.fail_on_empty_changset,
                tags=self.tags,
                region="us-west-2",
                profile=self.profile,
                confirm_changeset=True,
            )

            context_mock.run.assert_called_with()
            mock_save_config.assert_called_with(
                {
                    "Myparameter": {"Value": "guidedParameter", "Hidden": False},
                    "MyNoEchoParameter": {"Value": "secure", "Hidden": True},
                },
                capabilities=("CAPABILITY_IAM",),
                confirm_changeset=True,
                profile=self.profile,
                region="us-west-2",
                s3_bucket="managed-s3-bucket",
                stack_name="sam-app",
                s3_prefix="sam-app",
            )
            mock_managed_stack.assert_called_with(profile=self.profile, region="us-west-2")
            self.assertEqual(context_mock.run.call_count, 1)

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.command.print_deploy_args")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch.object(
        GuidedConfig,
        "get_config_ctx",
        MagicMock(return_value=(MockContext(info_name="deploy", parent=None), MOCK_SAM_CONFIG)),
    )
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    def test_all_args_guided_no_save_echo_param_to_config(
        self,
        mock_confirm,
        mock_prompt,
        mock_get_template_parameters,
        mock_managed_stack,
        mock_print_deploy_args,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):

        context_mock = Mock()
        mock_get_template_parameters.return_value = {
            "Myparameter": {"Type": "String"},
            "MyParameterSpaces": {"Type": "String"},
            "MyNoEchoParameter": {"Type": "String", "NoEcho": True},
        }
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_prompt.side_effect = [
            "sam-app",
            "us-west-2",
            "guidedParameter",
            "guided parameter with spaces",
            "secure",
            ("CAPABILITY_IAM",),
        ]
        mock_confirm.side_effect = [True, False, True]

        mock_managed_stack.return_value = "managed-s3-bucket"

        do_cli(
            template_file=self.template_file,
            stack_name=self.stack_name,
            s3_bucket=None,
            force_upload=self.force_upload,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            no_execute_changeset=self.no_execute_changeset,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            fail_on_empty_changeset=self.fail_on_empty_changset,
            tags=self.tags,
            region=self.region,
            profile=self.profile,
            use_json=self.use_json,
            metadata=self.metadata,
            guided=True,
            confirm_changeset=True,
        )

        mock_deploy_context.assert_called_with(
            template_file=ANY,
            stack_name="sam-app",
            s3_bucket="managed-s3-bucket",
            force_upload=self.force_upload,
            s3_prefix="sam-app",
            kms_key_id=self.kms_key_id,
            parameter_overrides={
                "Myparameter": "guidedParameter",
                "MyParameterSpaces": "guided parameter with spaces",
                "MyNoEchoParameter": "secure",
            },
            capabilities=self.capabilities,
            no_execute_changeset=self.no_execute_changeset,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            fail_on_empty_changeset=self.fail_on_empty_changset,
            tags=self.tags,
            region="us-west-2",
            profile=self.profile,
            confirm_changeset=True,
        )

        context_mock.run.assert_called_with()
        mock_managed_stack.assert_called_with(profile=self.profile, region="us-west-2")
        self.assertEqual(context_mock.run.call_count, 1)

        self.assertEqual(MOCK_SAM_CONFIG.put.call_count, 7)
        self.assertEqual(
            MOCK_SAM_CONFIG.put.call_args_list,
            [
                call(["deploy"], "parameters", "stack_name", "sam-app"),
                call(["deploy"], "parameters", "s3_bucket", "managed-s3-bucket"),
                call(["deploy"], "parameters", "s3_prefix", "sam-app"),
                call(["deploy"], "parameters", "region", "us-west-2"),
                call(["deploy"], "parameters", "confirm_changeset", True),
                call(["deploy"], "parameters", "capabilities", "CAPABILITY_IAM"),
                call(
                    ["deploy"],
                    "parameters",
                    "parameter_overrides",
                    'Myparameter="guidedParameter" MyParameterSpaces="guided parameter with spaces"',
                ),
            ],
        )

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.command.print_deploy_args")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch.object(
        GuidedConfig,
        "get_config_ctx",
        MagicMock(return_value=(MockContext(info_name="deploy", parent=None), MOCK_SAM_CONFIG)),
    )
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_config.SamConfig")
    @patch("samcli.commands.deploy.guided_config.get_cmd_names")
    def test_all_args_guided_no_params_save_config(
        self,
        mock_get_cmd_names,
        mock_sam_config,
        mock_confirm,
        mock_prompt,
        mock_get_template_parameters,
        mock_managed_stack,
        mock_print_deploy_args,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):

        context_mock = Mock()

        mock_get_template_parameters.return_value = {}
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_prompt.side_effect = ["sam-app", "us-west-2", ("CAPABILITY_IAM",)]
        mock_confirm.side_effect = [True, False, True]
        mock_get_cmd_names.return_value = ["deploy"]
        mock_managed_stack.return_value = "managed-s3-bucket"

        do_cli(
            template_file=self.template_file,
            stack_name=self.stack_name,
            s3_bucket=None,
            force_upload=self.force_upload,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            no_execute_changeset=self.no_execute_changeset,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            fail_on_empty_changeset=self.fail_on_empty_changset,
            tags=self.tags,
            region=self.region,
            profile=self.profile,
            use_json=self.use_json,
            metadata=self.metadata,
            guided=True,
            confirm_changeset=True,
        )

        mock_deploy_context.assert_called_with(
            template_file=ANY,
            stack_name="sam-app",
            s3_bucket="managed-s3-bucket",
            force_upload=self.force_upload,
            s3_prefix="sam-app",
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            no_execute_changeset=self.no_execute_changeset,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            fail_on_empty_changeset=self.fail_on_empty_changset,
            tags=self.tags,
            region="us-west-2",
            profile=self.profile,
            confirm_changeset=True,
        )

        context_mock.run.assert_called_with()
        mock_managed_stack.assert_called_with(profile=self.profile, region="us-west-2")
        self.assertEqual(context_mock.run.call_count, 1)

        self.assertEqual(MOCK_SAM_CONFIG.put.call_count, 7)
        self.assertEqual(
            MOCK_SAM_CONFIG.put.call_args_list,
            [
                call(["deploy"], "parameters", "stack_name", "sam-app"),
                call(["deploy"], "parameters", "s3_bucket", "managed-s3-bucket"),
                call(["deploy"], "parameters", "s3_prefix", "sam-app"),
                call(["deploy"], "parameters", "region", "us-west-2"),
                call(["deploy"], "parameters", "confirm_changeset", True),
                call(["deploy"], "parameters", "capabilities", "CAPABILITY_IAM"),
                call(["deploy"], "parameters", "parameter_overrides", 'a="b"'),
            ],
        )

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.command.print_deploy_args")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch.object(GuidedConfig, "get_config_ctx", MagicMock(return_value=(None, get_mock_sam_config())))
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    def test_all_args_guided_no_params_no_save_config(
        self,
        mock_confirm,
        mock_prompt,
        mock_get_template_parameters,
        mock_managed_stack,
        mock_print_deploy_args,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):

        context_mock = Mock()
        mock_get_template_parameters.return_value = {}
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_prompt.side_effect = ["sam-app", "us-west-2", ("CAPABILITY_IAM",)]
        mock_confirm.side_effect = [True, False, False]

        mock_managed_stack.return_value = "managed-s3-bucket"

        with patch.object(GuidedConfig, "save_config", MagicMock(return_value=False)) as mock_save_config:

            do_cli(
                template_file=self.template_file,
                stack_name=self.stack_name,
                s3_bucket=None,
                force_upload=self.force_upload,
                s3_prefix=self.s3_prefix,
                kms_key_id=self.kms_key_id,
                parameter_overrides=self.parameter_overrides,
                capabilities=self.capabilities,
                no_execute_changeset=self.no_execute_changeset,
                role_arn=self.role_arn,
                notification_arns=self.notification_arns,
                fail_on_empty_changeset=self.fail_on_empty_changset,
                tags=self.tags,
                region=self.region,
                profile=self.profile,
                use_json=self.use_json,
                metadata=self.metadata,
                guided=True,
                confirm_changeset=True,
            )

            mock_deploy_context.assert_called_with(
                template_file=ANY,
                stack_name="sam-app",
                s3_bucket="managed-s3-bucket",
                force_upload=self.force_upload,
                s3_prefix="sam-app",
                kms_key_id=self.kms_key_id,
                parameter_overrides=self.parameter_overrides,
                capabilities=self.capabilities,
                no_execute_changeset=self.no_execute_changeset,
                role_arn=self.role_arn,
                notification_arns=self.notification_arns,
                fail_on_empty_changeset=self.fail_on_empty_changset,
                tags=self.tags,
                region="us-west-2",
                profile=self.profile,
                confirm_changeset=True,
            )

            context_mock.run.assert_called_with()
            self.assertEqual(mock_save_config.call_count, 0)
            mock_managed_stack.assert_called_with(profile=self.profile, region="us-west-2")
            self.assertEqual(context_mock.run.call_count, 1)
