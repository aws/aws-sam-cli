from unittest import TestCase
from unittest.mock import Mock, patch, call, MagicMock

from samcli.lib.pipeline.bootstrap.stage import Stage

ANY_STAGE_CONFIGURATION_NAME = "ANY_STAGE_CONFIGURATION_NAME"
ANY_PIPELINE_USER_ARN = "ANY_PIPELINE_USER_ARN"
ANY_PIPELINE_EXECUTION_ROLE_ARN = "ANY_PIPELINE_EXECUTION_ROLE_ARN"
ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN = "ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN"
ANY_ARTIFACTS_BUCKET_ARN = "ANY_ARTIFACTS_BUCKET_ARN"
ANY_IMAGE_REPOSITORY_ARN = "ANY_IMAGE_REPOSITORY_ARN"
ANY_ARN = "ANY_ARN"


class TestStage(TestCase):
    def test_stage_configuration_name_is_the_only_required_field_to_initialize_an_stage(self):
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        self.assertEqual(stage.name, ANY_STAGE_CONFIGURATION_NAME)
        self.assertIsNone(stage.aws_profile)
        self.assertIsNone(stage.aws_region)
        self.assertIsNotNone(stage.pipeline_user)
        self.assertIsNotNone(stage.pipeline_execution_role)
        self.assertIsNotNone(stage.cloudformation_execution_role)
        self.assertIsNotNone(stage.artifacts_bucket)
        self.assertIsNotNone(stage.image_repository)

        with self.assertRaises(TypeError):
            Stage()

    def test_did_user_provide_all_required_resources_when_not_all_resources_are_provided(self):
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        self.assertFalse(stage.did_user_provide_all_required_resources())
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME, pipeline_user_arn=ANY_PIPELINE_USER_ARN)
        self.assertFalse(stage.did_user_provide_all_required_resources())
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
        )
        self.assertFalse(stage.did_user_provide_all_required_resources())
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
        )
        self.assertFalse(stage.did_user_provide_all_required_resources())
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
        )
        self.assertFalse(stage.did_user_provide_all_required_resources())

    def test_did_user_provide_all_required_resources_ignore_image_repository_if_it_is_not_required(self):
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=False,
        )
        self.assertTrue(stage.did_user_provide_all_required_resources())

    def test_did_user_provide_all_required_resources_when_image_repository_is_required(self):
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
        )
        self.assertFalse(stage.did_user_provide_all_required_resources())
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
        )
        self.assertTrue(stage.did_user_provide_all_required_resources())

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.manage_stack")
    def test_did_user_provide_all_required_resources_returns_false_if_the_stage_was_initialized_without_any_of_the_resources_even_if_fulfilled_after_bootstrap(
        self, manage_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        # setup
        stack_output = Mock()
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stack_output.get.return_value = ANY_ARN
        manage_stack_mock.return_value = stack_output
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)

        self.assertFalse(stage.did_user_provide_all_required_resources())

        stage.bootstrap(confirm_changeset=False)
        # After bootstrapping, all the resources should be fulfilled
        self.assertEqual(ANY_ARN, stage.pipeline_user.arn)
        self.assertEqual(ANY_ARN, stage.pipeline_execution_role.arn)
        self.assertEqual(ANY_ARN, stage.cloudformation_execution_role.arn)
        self.assertEqual(ANY_ARN, stage.artifacts_bucket.arn)
        self.assertEqual(ANY_ARN, stage.image_repository.arn)

        # although all of the resources got fulfilled, `did_user_provide_all_required_resources` should return false
        # as these resources are not provided by the user
        self.assertFalse(stage.did_user_provide_all_required_resources())

    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.manage_stack")
    @patch.object(Stage, "did_user_provide_all_required_resources")
    def test_bootstrap_will_not_deploy_the_cfn_template_if_all_resources_are_already_provided(
        self, did_user_provide_all_required_resources_mock, manage_stack_mock, click_mock
    ):
        did_user_provide_all_required_resources_mock.return_value = True
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=False)
        manage_stack_mock.assert_not_called()

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.manage_stack")
    def test_bootstrap_will_confirm_before_deploying_unless_confirm_changeset_is_disabled(
        self, manage_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        click_mock.confirm.return_value = False
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=False)
        click_mock.confirm.assert_not_called()
        manage_stack_mock.assert_called_once()
        manage_stack_mock.reset_mock()
        stage.bootstrap(confirm_changeset=True)
        click_mock.confirm.assert_called_once()
        manage_stack_mock.assert_not_called()  # As the user choose to not confirm

    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.manage_stack")
    def test_bootstrap_will_not_deploy_the_cfn_template_if_the_user_did_not_confirm(
        self, manage_stack_mock, click_mock
    ):
        click_mock.confirm.return_value = False
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=True)
        manage_stack_mock.assert_not_called()

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.manage_stack")
    def test_bootstrap_will_deploy_the_cfn_template_if_the_user_did_confirm(
        self, manage_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        click_mock.confirm.return_value = True
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=True)
        manage_stack_mock.assert_called_once()

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.manage_stack")
    def test_bootstrap_will_pass_arns_of_all_user_provided_resources_any_empty_strings_for_other_resources_to_the_cfn_stack(
        self, manage_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        click_mock.confirm.return_value = True
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
        )
        stage.bootstrap()
        manage_stack_mock.assert_called_once()
        args, kwargs = manage_stack_mock.call_args_list[0]
        expected_parameter_overrides = {
            "PipelineUserArn": ANY_PIPELINE_USER_ARN,
            "PipelineExecutionRoleArn": "",
            "CloudFormationExecutionRoleArn": "",
            "ArtifactsBucketArn": ANY_ARTIFACTS_BUCKET_ARN,
            "CreateImageRepository": "true",
            "ImageRepositoryArn": ANY_IMAGE_REPOSITORY_ARN,
        }
        self.assertEqual(expected_parameter_overrides, kwargs["parameter_overrides"])

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.manage_stack")
    def test_bootstrap_will_fullfill_all_resource_arns(
        self, manage_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        # setup
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stack_output = Mock()
        stack_output.get.return_value = ANY_ARN
        manage_stack_mock.return_value = stack_output
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        click_mock.confirm.return_value = True

        # verify resources' ARNS are empty
        self.assertIsNone(stage.pipeline_user.arn)
        self.assertIsNone(stage.pipeline_execution_role.arn)
        self.assertIsNone(stage.cloudformation_execution_role.arn)
        self.assertIsNone(stage.artifacts_bucket.arn)

        # trigger
        stage.bootstrap()

        # verify
        manage_stack_mock.assert_called_once()
        self.assertEqual(ANY_ARN, stage.pipeline_user.arn)
        self.assertEqual(ANY_ARN, stage.pipeline_execution_role.arn)
        self.assertEqual(ANY_ARN, stage.cloudformation_execution_role.arn)
        self.assertEqual(ANY_ARN, stage.artifacts_bucket.arn)

    @patch("samcli.lib.pipeline.bootstrap.stage.SamConfig")
    def test_save_config_escapes_none_resources(self, samconfig_mock):
        cmd_names = ["any", "commands"]
        samconfig_instance_mock = Mock()
        samconfig_mock.return_value = samconfig_instance_mock
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)

        empty_ecr_call = call(
            cmd_names=cmd_names,
            section="parameters",
            env=ANY_STAGE_CONFIGURATION_NAME,
            key="image_repository",
            value="",
        )

        expected_calls = []
        self.trigger_and_assert_save_config_calls(
            stage, cmd_names, expected_calls + [empty_ecr_call], samconfig_instance_mock.put
        )

        stage.pipeline_user.arn = ANY_PIPELINE_USER_ARN
        expected_calls.append(
            call(cmd_names=cmd_names, section="parameters", key="pipeline_user", value=ANY_PIPELINE_USER_ARN)
        )
        self.trigger_and_assert_save_config_calls(
            stage, cmd_names, expected_calls + [empty_ecr_call], samconfig_instance_mock.put
        )

        stage.pipeline_execution_role.arn = ANY_PIPELINE_EXECUTION_ROLE_ARN
        expected_calls.append(
            call(
                cmd_names=cmd_names,
                section="parameters",
                env=ANY_STAGE_CONFIGURATION_NAME,
                key="pipeline_execution_role",
                value=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            ),
        )
        self.trigger_and_assert_save_config_calls(
            stage, cmd_names, expected_calls + [empty_ecr_call], samconfig_instance_mock.put
        )

        stage.cloudformation_execution_role.arn = ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN
        expected_calls.append(
            call(
                cmd_names=cmd_names,
                section="parameters",
                env=ANY_STAGE_CONFIGURATION_NAME,
                key="cloudformation_execution_role",
                value=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            ),
        )
        self.trigger_and_assert_save_config_calls(
            stage, cmd_names, expected_calls + [empty_ecr_call], samconfig_instance_mock.put
        )

        stage.artifacts_bucket.arn = "arn:aws:s3:::artifact_bucket_name"
        expected_calls.append(
            call(
                cmd_names=cmd_names,
                section="parameters",
                env=ANY_STAGE_CONFIGURATION_NAME,
                key="artifacts_bucket",
                value="artifact_bucket_name",
            ),
        )
        self.trigger_and_assert_save_config_calls(
            stage, cmd_names, expected_calls + [empty_ecr_call], samconfig_instance_mock.put
        )

        stage.image_repository.arn = "arn:aws:ecr:us-east-2:111111111111:repository/image_repository_name"
        expected_calls.append(
            call(
                cmd_names=cmd_names,
                section="parameters",
                env=ANY_STAGE_CONFIGURATION_NAME,
                key="image_repository",
                value="111111111111.dkr.ecr.us-east-2.amazonaws.com/image_repository_name",
            )
        )
        self.trigger_and_assert_save_config_calls(stage, cmd_names, expected_calls, samconfig_instance_mock.put)

    def trigger_and_assert_save_config_calls(self, stage, cmd_names, expected_calls, samconfig_put_mock):
        stage.save_config(config_dir="any_config_dir", filename="any_pipeline.toml", cmd_names=cmd_names)
        self.assertEqual(len(expected_calls), samconfig_put_mock.call_count)
        samconfig_put_mock.assert_has_calls(expected_calls, any_order=True)
        samconfig_put_mock.reset_mock()

    @patch("samcli.lib.pipeline.bootstrap.stage.boto3")
    def test_getting_pipeline_user_credentials(self, boto3_mock):
        sm_client_mock = MagicMock()
        sm_client_mock.get_secret_value.return_value = {
            "SecretString": '{"aws_access_key_id": "AccessKeyId", "aws_secret_access_key": "SuperSecretKey"}'
        }
        session_mock = MagicMock()
        session_mock.client.return_value = sm_client_mock
        boto3_mock.Session.return_value = session_mock

        (key, secret) = Stage._get_pipeline_user_secret_pair("dummy_arn", None, "dummy-region")
        self.assertEqual(key, "AccessKeyId")
        self.assertEqual(secret, "SuperSecretKey")
        sm_client_mock.get_secret_value.assert_called_once_with(SecretId="dummy_arn")

    @patch("samcli.lib.pipeline.bootstrap.stage.SamConfig")
    def test_save_config_ignores_exceptions_thrown_while_calculating_artifacts_bucket_name(self, samconfig_mock):
        samconfig_instance_mock = Mock()
        samconfig_mock.return_value = samconfig_instance_mock
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME, artifacts_bucket_arn="invalid ARN")
        # calling artifacts_bucket.name() during save_config() will raise a ValueError exception, we need to make sure
        # this exception is swallowed so that other configs can be safely saved to the pipelineconfig.toml file
        stage.save_config(config_dir="any_config_dir", filename="any_pipeline.toml", cmd_names=["any", "commands"])

    @patch("samcli.lib.pipeline.bootstrap.stage.SamConfig")
    def test_save_config_ignores_exceptions_thrown_while_calculating_image_repository_uri(self, samconfig_mock):
        samconfig_instance_mock = Mock()
        samconfig_mock.return_value = samconfig_instance_mock
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME, image_repository_arn="invalid ARN")
        # calling image_repository.get_uri() during save_config() will raise a ValueError exception, we need to make
        # sure this exception is swallowed so that other configs can be safely saved to the pipelineconfig.toml file
        stage.save_config(config_dir="any_config_dir", filename="any_pipeline.toml", cmd_names=["any", "commands"])

    @patch.object(Stage, "save_config")
    def test_save_config_safe(self, save_config_mock):
        save_config_mock.side_effect = Exception
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.save_config_safe(config_dir="any_config_dir", filename="any_pipeline.toml", cmd_names=["commands"])
        save_config_mock.assert_called_once_with("any_config_dir", "any_pipeline.toml", ["commands"])

    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    def test_print_resources_summary_when_no_resources_provided_by_the_user(self, click_mock):
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.print_resources_summary()
        self.assert_summary_has_a_message_like("The following resources were created in your account", click_mock.secho)

    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    def test_print_resources_summary_when_all_resources_are_provided_by_the_user(self, click_mock):
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
        )
        stage.print_resources_summary()
        self.assert_summary_does_not_have_a_message_like(
            "The following resources were created in your account", click_mock.secho
        )

    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    def test_print_resources_summary_when_some_resources_are_provided_by_the_user(self, click_mock):
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
        )
        stage.print_resources_summary()
        self.assert_summary_has_a_message_like("The following resources were created in your account", click_mock.secho)

    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    def test_print_resources_summary_prints_the_credentials_of_the_pipeline_user_iff_not_provided_by_the_user(
        self, click_mock
    ):
        stage_with_provided_pipeline_user: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME, pipeline_user_arn=ANY_PIPELINE_USER_ARN
        )
        stage_with_provided_pipeline_user.print_resources_summary()
        self.assert_summary_does_not_have_a_message_like("AWS_ACCESS_KEY_ID", click_mock.secho)
        self.assert_summary_does_not_have_a_message_like("AWS_SECRET_ACCESS_KEY", click_mock.secho)
        click_mock.secho.reset_mock()

        stage_without_provided_pipeline_user: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage_without_provided_pipeline_user.print_resources_summary()
        self.assert_summary_has_a_message_like("AWS_ACCESS_KEY_ID", click_mock.secho)
        self.assert_summary_has_a_message_like("AWS_SECRET_ACCESS_KEY", click_mock.secho)

    def assert_summary_has_a_message_like(self, msg, click_secho_mock):
        self.assertTrue(
            self.does_summary_have_a_message_like(msg, click_secho_mock),
            msg=f'stage resources summary does not include "{msg}" which is unexpected',
        )

    def assert_summary_does_not_have_a_message_like(self, msg, click_secho_mock):
        self.assertFalse(
            self.does_summary_have_a_message_like(msg, click_secho_mock),
            msg=f'stage resources summary includes "{msg}" which is unexpected',
        )

    @staticmethod
    def does_summary_have_a_message_like(msg, click_secho_mock):
        msg = msg.lower()
        for kall in click_secho_mock.call_args_list:
            args, kwargs = kall
            if args:
                message = args[0].lower()
            else:
                message = kwargs.get("message", "").lower()
            if msg in message:
                return True
        return False
