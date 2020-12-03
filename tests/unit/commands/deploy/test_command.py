from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, call, patch

from samcli.commands.deploy.command import do_cli
from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.commands.deploy.guided_config import GuidedConfig
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.commands.deploy.exceptions import DeployResolveS3AndS3SetError
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
        self.image_repository = "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"
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
        self.no_progressbar = False
        self.metadata = {"abc": "def"}
        self.region = None
        self.profile = None
        self.use_json = True
        self.metadata = {}
        self.guided = False
        self.confirm_changeset = False
        self.resolve_s3 = False
        self.config_env = "mock-default-env"
        self.config_file = "mock-default-filename"
        self.signing_profiles = None
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
            image_repository=self.image_repository,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
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
            signing_profiles=self.signing_profiles,
            resolve_s3=self.resolve_s3,
            config_env=self.config_env,
            config_file=self.config_file,
        )

        mock_deploy_context.assert_called_with(
            template_file=ANY,
            stack_name=self.stack_name,
            s3_bucket=self.s3_bucket,
            image_repository=self.image_repository,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
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
            signing_profiles=self.signing_profiles,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    @patch("samcli.commands.deploy.guided_context.get_template_artifacts_format")
    @patch("samcli.commands.deploy.guided_context.transform_template")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    @patch.object(GuidedConfig, "get_config_ctx", MagicMock(return_value=(None, get_mock_sam_config())))
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    def test_all_args_guided_no_to_authorization_confirmation_prompt(
        self,
        mock_confirm,
        mock_prompt,
        mock_signer_config_per_function,
        mock_transform_template,
        mock_get_template_artifacts_format,
        mock_get_template_data,
        mock_get_template_parameters,
        mockauth_per_resource,
        mock_managed_stack,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):

        mock_transform_template.return_value = {}
        mock_get_template_artifacts_format.return_value = [ZIP]
        context_mock = Mock()
        mockauth_per_resource.return_value = [("HelloWorldResource1", False), ("HelloWorldResource2", False)]
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_confirm.side_effect = [True, True, True, False]
        mock_prompt.side_effect = [
            "sam-app",
            "us-east-1",
            "guidedParameter",
            "secure",
            ("CAPABILITY_IAM",),
            "testconfig.toml",
            "test-env",
        ]

        mock_get_template_parameters.return_value = {
            "Myparameter": {"Type": "String"},
            "MyNoEchoParameter": {"Type": "String", "NoEcho": True},
        }

        mock_managed_stack.return_value = "managed-s3-bucket"
        mock_signer_config_per_function.return_value = ({}, {})

        with patch.object(GuidedConfig, "save_config", MagicMock(return_value=True)) as mock_save_config:
            with self.assertRaises(GuidedDeployFailedError):
                do_cli(
                    template_file=self.template_file,
                    stack_name=self.stack_name,
                    s3_bucket=None,
                    image_repository=None,
                    force_upload=self.force_upload,
                    no_progressbar=self.no_progressbar,
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
                    signing_profiles=self.signing_profiles,
                    resolve_s3=self.resolve_s3,
                    config_env=self.config_env,
                    config_file=self.config_file,
                )

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    @patch("samcli.commands.deploy.guided_context.get_template_artifacts_format")
    @patch("samcli.commands.deploy.guided_context.transform_template")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    @patch.object(GuidedConfig, "get_config_ctx", MagicMock(return_value=(None, get_mock_sam_config())))
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.tag_translation")
    def test_all_args_guided(
        self,
        mock_tag_translation,
        mock_confirm,
        mock_prompt,
        mock_signer_config_per_function,
        mock_transform_template,
        mock_get_template_artifacts_format,
        mock_get_template_data,
        mock_get_template_parameters,
        mockauth_per_resource,
        mock_managed_stack,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):
        mock_tag_translation.return_value = "helloworld-123456-v1"

        context_mock = Mock()
        mock_transform_template.return_value = MagicMock(
            functions={"HelloWorldFunction": MagicMock(packagetype=IMAGE, imageuri="helloworld:v1")}
        )
        mock_get_template_artifacts_format.return_value = [IMAGE]
        mockauth_per_resource.return_value = [("HelloWorldResource", False)]
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_confirm.side_effect = [True, False, True, True]
        mock_prompt.side_effect = [
            "sam-app",
            "us-east-1",
            "guidedParameter",
            "secure",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            ("CAPABILITY_IAM",),
            "testconfig.toml",
            "test-env",
        ]

        mock_get_template_parameters.return_value = {
            "Myparameter": {"Type": "String"},
            "MyNoEchoParameter": {"Type": "String", "NoEcho": True},
        }

        mock_managed_stack.return_value = "managed-s3-bucket"

        mock_signer_config_per_function.return_value = ({}, {})

        with patch.object(GuidedConfig, "save_config", MagicMock(return_value=True)) as mock_save_config:
            do_cli(
                template_file=self.template_file,
                stack_name=self.stack_name,
                s3_bucket=None,
                image_repository=None,
                force_upload=self.force_upload,
                no_progressbar=self.no_progressbar,
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
                signing_profiles=self.signing_profiles,
                resolve_s3=self.resolve_s3,
                config_env=self.config_env,
                config_file=self.config_file,
            )

            mock_deploy_context.assert_called_with(
                template_file=ANY,
                stack_name="sam-app",
                s3_bucket="managed-s3-bucket",
                image_repository="123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                force_upload=self.force_upload,
                no_progressbar=self.no_progressbar,
                s3_prefix="sam-app",
                kms_key_id=self.kms_key_id,
                parameter_overrides={"Myparameter": "guidedParameter", "MyNoEchoParameter": "secure"},
                capabilities=self.capabilities,
                no_execute_changeset=self.no_execute_changeset,
                role_arn=self.role_arn,
                notification_arns=self.notification_arns,
                fail_on_empty_changeset=self.fail_on_empty_changset,
                tags=self.tags,
                region="us-east-1",
                profile=self.profile,
                confirm_changeset=True,
                signing_profiles=self.signing_profiles,
            )

            context_mock.run.assert_called_with()
            mock_save_config.assert_called_with(
                {
                    "Myparameter": {"Value": "guidedParameter", "Hidden": False},
                    "MyNoEchoParameter": {"Value": "secure", "Hidden": True},
                },
                "test-env",
                "testconfig.toml",
                capabilities=("CAPABILITY_IAM",),
                confirm_changeset=True,
                profile=self.profile,
                region="us-east-1",
                s3_bucket="managed-s3-bucket",
                image_repository="123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                stack_name="sam-app",
                s3_prefix="sam-app",
                signing_profiles=self.signing_profiles,
            )
            mock_managed_stack.assert_called_with(profile=self.profile, region="us-east-1")
            self.assertEqual(context_mock.run.call_count, 1)

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.get_template_artifacts_format")
    @patch("samcli.commands.deploy.guided_context.transform_template")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    @patch.object(
        GuidedConfig,
        "get_config_ctx",
        MagicMock(return_value=(MockContext(info_name="deploy", parent=None), MOCK_SAM_CONFIG)),
    )
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.tag_translation")
    def test_all_args_guided_no_save_echo_param_to_config(
        self,
        mock_tag_translation,
        mock_confirm,
        mock_prompt,
        mock_signer_config_per_function,
        mock_transform_template,
        mock_get_template_artifacts_format,
        mock_get_template_parameters,
        mock_get_template_data,
        mockauth_per_resource,
        mock_managed_stack,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):
        mock_tag_translation.return_value = "helloworld-123456-v1"

        context_mock = Mock()
        mock_transform_template.return_value = MagicMock(
            functions={"HelloWorldFunction": MagicMock(packagetype=IMAGE, imageuri="helloworld:v1")}
        )
        mock_get_template_artifacts_format.return_value = [IMAGE]
        mockauth_per_resource.return_value = [("HelloWorldResource", False)]
        mock_get_template_parameters.return_value = {
            "Myparameter": {"Type": "String"},
            "MyParameterSpaces": {"Type": "String"},
            "MyNoEchoParameter": {"Type": "String", "NoEcho": True},
        }
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_prompt.side_effect = [
            "sam-app",
            "us-east-1",
            "guidedParameter",
            "guided parameter with spaces",
            "secure",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            ("CAPABILITY_IAM",),
            "testconfig.toml",
            "test-env",
        ]
        mock_confirm.side_effect = [True, False, True, True]

        mock_managed_stack.return_value = "managed-s3-bucket"
        mock_signer_config_per_function.return_value = ({}, {})

        do_cli(
            template_file=self.template_file,
            stack_name=self.stack_name,
            s3_bucket=None,
            image_repository=None,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
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
            signing_profiles=self.signing_profiles,
            resolve_s3=self.resolve_s3,
            config_env=self.config_env,
            config_file=self.config_file,
        )

        mock_deploy_context.assert_called_with(
            template_file=ANY,
            stack_name="sam-app",
            s3_bucket="managed-s3-bucket",
            image_repository="123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
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
            region="us-east-1",
            profile=self.profile,
            confirm_changeset=True,
            signing_profiles=self.signing_profiles,
        )

        context_mock.run.assert_called_with()
        mock_managed_stack.assert_called_with(profile=self.profile, region="us-east-1")
        self.assertEqual(context_mock.run.call_count, 1)

        self.assertEqual(MOCK_SAM_CONFIG.put.call_count, 8)
        self.assertEqual(
            MOCK_SAM_CONFIG.put.call_args_list,
            [
                call(["deploy"], "parameters", "stack_name", "sam-app", env="test-env"),
                call(["deploy"], "parameters", "s3_bucket", "managed-s3-bucket", env="test-env"),
                call(["deploy"], "parameters", "s3_prefix", "sam-app", env="test-env"),
                call(
                    ["deploy"],
                    "parameters",
                    "image_repository",
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                    env="test-env",
                ),
                call(["deploy"], "parameters", "region", "us-east-1", env="test-env"),
                call(["deploy"], "parameters", "confirm_changeset", True, env="test-env"),
                call(["deploy"], "parameters", "capabilities", "CAPABILITY_IAM", env="test-env"),
                call(
                    ["deploy"],
                    "parameters",
                    "parameter_overrides",
                    'Myparameter="guidedParameter" MyParameterSpaces="guided parameter with spaces"',
                    env="test-env",
                ),
            ],
        )

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    @patch("samcli.commands.deploy.guided_context.get_template_artifacts_format")
    @patch("samcli.commands.deploy.guided_context.transform_template")
    @patch.object(
        GuidedConfig,
        "get_config_ctx",
        MagicMock(return_value=(MockContext(info_name="deploy", parent=None), MOCK_SAM_CONFIG)),
    )
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_config.SamConfig")
    @patch("samcli.commands.deploy.guided_config.get_cmd_names")
    @patch("samcli.commands.deploy.guided_context.tag_translation")
    def test_all_args_guided_no_params_save_config(
        self,
        mock_tag_translation,
        mock_get_cmd_names,
        mock_sam_config,
        mock_confirm,
        mock_prompt,
        mock_transform_template,
        mock_get_template_artifacts_format,
        mock_signer_config_per_function,
        mock_get_template_parameters,
        mock_managed_stack,
        mock_get_template_data,
        mockauth_per_resource,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):
        mock_tag_translation.return_value = "helloworld-123456-v1"

        context_mock = Mock()
        mock_transform_template.return_value = MagicMock(
            functions={"HelloWorldFunction": MagicMock(packagetype=IMAGE, imageuri="helloworld:v1")}
        )
        mock_get_template_artifacts_format.return_value = [IMAGE]
        mockauth_per_resource.return_value = [("HelloWorldResource", False)]

        mock_get_template_parameters.return_value = {}
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_prompt.side_effect = [
            "sam-app",
            "us-east-1",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            ("CAPABILITY_IAM",),
            "testconfig.toml",
            "test-env",
        ]
        mock_confirm.side_effect = [True, False, True, True]
        mock_get_cmd_names.return_value = ["deploy"]
        mock_managed_stack.return_value = "managed-s3-bucket"
        mock_signer_config_per_function.return_value = ({}, {})

        do_cli(
            template_file=self.template_file,
            stack_name=self.stack_name,
            s3_bucket=None,
            image_repository=None,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
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
            resolve_s3=self.resolve_s3,
            config_env=self.config_env,
            config_file=self.config_file,
            signing_profiles=self.signing_profiles,
        )

        mock_deploy_context.assert_called_with(
            template_file=ANY,
            stack_name="sam-app",
            s3_bucket="managed-s3-bucket",
            image_repository="123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
            s3_prefix="sam-app",
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            no_execute_changeset=self.no_execute_changeset,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            fail_on_empty_changeset=self.fail_on_empty_changset,
            tags=self.tags,
            region="us-east-1",
            profile=self.profile,
            confirm_changeset=True,
            signing_profiles=self.signing_profiles,
        )

        context_mock.run.assert_called_with()
        mock_managed_stack.assert_called_with(profile=self.profile, region="us-east-1")
        self.assertEqual(context_mock.run.call_count, 1)

        self.assertEqual(MOCK_SAM_CONFIG.put.call_count, 8)
        self.assertEqual(
            MOCK_SAM_CONFIG.put.call_args_list,
            [
                call(["deploy"], "parameters", "stack_name", "sam-app", env="test-env"),
                call(["deploy"], "parameters", "s3_bucket", "managed-s3-bucket", env="test-env"),
                call(["deploy"], "parameters", "s3_prefix", "sam-app", env="test-env"),
                call(
                    ["deploy"],
                    "parameters",
                    "image_repository",
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                    env="test-env",
                ),
                call(["deploy"], "parameters", "region", "us-east-1", env="test-env"),
                call(["deploy"], "parameters", "confirm_changeset", True, env="test-env"),
                call(["deploy"], "parameters", "capabilities", "CAPABILITY_IAM", env="test-env"),
                call(["deploy"], "parameters", "parameter_overrides", 'a="b"', env="test-env"),
            ],
        )

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.guided_context.manage_stack")
    @patch("samcli.commands.deploy.guided_context.auth_per_resource")
    @patch("samcli.commands.deploy.guided_context.get_template_data")
    @patch("samcli.commands.deploy.guided_context.get_template_parameters")
    @patch("samcli.commands.deploy.guided_context.get_template_artifacts_format")
    @patch("samcli.commands.deploy.guided_context.transform_template")
    @patch("samcli.commands.deploy.guided_context.signer_config_per_function")
    @patch.object(GuidedConfig, "get_config_ctx", MagicMock(return_value=(None, get_mock_sam_config())))
    @patch("samcli.commands.deploy.guided_context.prompt")
    @patch("samcli.commands.deploy.guided_context.confirm")
    @patch("samcli.commands.deploy.guided_context.tag_translation")
    def test_all_args_guided_no_params_no_save_config(
        self,
        mock_tag_translation,
        mock_confirm,
        mock_prompt,
        mock_signer_config_per_function,
        mock_transform_template,
        mock_get_template_artifacts_format,
        mock_get_template_parameters,
        mock_get_template_data,
        mockauth_per_resource,
        mock_managed_stack,
        mock_deploy_context,
        mock_deploy_click,
        mock_package_context,
        mock_package_click,
    ):
        mock_tag_translation.return_value = "helloworld-123456-v1"

        context_mock = Mock()
        mock_transform_template.return_value = MagicMock(
            functions={"HelloWorldFunction": MagicMock(packagetype=IMAGE, imageuri="helloworld:v1")}
        )
        mock_get_template_artifacts_format.return_value = [IMAGE]
        mockauth_per_resource.return_value = [("HelloWorldResource", False)]
        mock_get_template_parameters.return_value = {}
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_prompt.side_effect = [
            "sam-app",
            "us-east-1",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            ("CAPABILITY_IAM",),
        ]
        mock_confirm.side_effect = [True, False, True, False]

        mock_managed_stack.return_value = "managed-s3-bucket"
        mock_signer_config_per_function.return_value = ({}, {})

        with patch.object(GuidedConfig, "save_config", MagicMock(return_value=False)) as mock_save_config:

            do_cli(
                template_file=self.template_file,
                stack_name=self.stack_name,
                s3_bucket=None,
                image_repository=None,
                force_upload=self.force_upload,
                no_progressbar=self.no_progressbar,
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
                resolve_s3=self.resolve_s3,
                config_file=self.config_file,
                config_env=self.config_env,
                signing_profiles=self.signing_profiles,
            )

            mock_deploy_context.assert_called_with(
                template_file=ANY,
                stack_name="sam-app",
                s3_bucket="managed-s3-bucket",
                image_repository="123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                force_upload=self.force_upload,
                no_progressbar=self.no_progressbar,
                s3_prefix="sam-app",
                kms_key_id=self.kms_key_id,
                parameter_overrides=self.parameter_overrides,
                capabilities=self.capabilities,
                no_execute_changeset=self.no_execute_changeset,
                role_arn=self.role_arn,
                notification_arns=self.notification_arns,
                fail_on_empty_changeset=self.fail_on_empty_changset,
                tags=self.tags,
                region="us-east-1",
                profile=self.profile,
                confirm_changeset=True,
                signing_profiles=self.signing_profiles,
            )

            context_mock.run.assert_called_with()
            self.assertEqual(mock_save_config.call_count, 0)
            mock_managed_stack.assert_called_with(profile=self.profile, region="us-east-1")
            self.assertEqual(context_mock.run.call_count, 1)

    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.deploy.command.manage_stack")
    def test_all_args_resolve_s3(
        self, mock_manage_stack, mock_deploy_context, mock_deploy_click, mock_package_context, mock_package_click
    ):
        context_mock = Mock()
        mock_deploy_context.return_value.__enter__.return_value = context_mock
        mock_manage_stack.return_value = "managed-s3-bucket"

        do_cli(
            template_file=self.template_file,
            stack_name=self.stack_name,
            s3_bucket=None,
            image_repository=None,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
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
            resolve_s3=True,
            config_file=self.config_file,
            config_env=self.config_env,
            signing_profiles=self.signing_profiles,
        )

        mock_deploy_context.assert_called_with(
            template_file=ANY,
            stack_name=self.stack_name,
            s3_bucket="managed-s3-bucket",
            force_upload=self.force_upload,
            image_repository=None,
            no_progressbar=self.no_progressbar,
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
            signing_profiles=self.signing_profiles,
        )

        context_mock.run.assert_called_with()
        self.assertEqual(context_mock.run.call_count, 1)

    def test_resolve_s3_and_s3_bucket_both_set(self):
        with self.assertRaises(DeployResolveS3AndS3SetError):
            do_cli(
                template_file=self.template_file,
                stack_name=self.stack_name,
                s3_bucket="managed-s3-bucket",
                image_repository=None,
                force_upload=self.force_upload,
                no_progressbar=self.no_progressbar,
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
                guided=False,
                confirm_changeset=True,
                resolve_s3=True,
                config_file=self.config_file,
                config_env=self.config_env,
                signing_profiles=self.signing_profiles,
            )
