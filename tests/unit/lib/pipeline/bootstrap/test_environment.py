import hashlib
from unittest import TestCase
from unittest.mock import Mock, patch, call, MagicMock

import OpenSSL.SSL  # type: ignore
import requests

from samcli.commands.pipeline.bootstrap.guided_context import GITHUB_ACTIONS
from samcli.lib.pipeline.bootstrap.stage import Stage, _get_secure_ssl_context

ANY_STAGE_CONFIGURATION_NAME = "ANY_STAGE_CONFIGURATION_NAME"
ANY_PIPELINE_USER_ARN = "ANY_PIPELINE_USER_ARN"
ANY_PIPELINE_EXECUTION_ROLE_ARN = "ANY_PIPELINE_EXECUTION_ROLE_ARN"
ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN = "ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN"
ANY_ARTIFACTS_BUCKET_ARN = "ANY_ARTIFACTS_BUCKET_ARN"
ANY_IMAGE_REPOSITORY_ARN = "ANY_IMAGE_REPOSITORY_ARN"
ANY_ARN = "ANY_ARN"
ANY_OIDC_PROVIDER_URL = "ANY_OIDC_PROVIDER_URL"
ANY_OIDC_CLIENT_ID = "ANY_OIDC_CLIENT_ID"
ANY_OIDC_PROVIDER = "ANY_OIDC_PROVIDER"
ANY_SUBJECT_CLAIM = "ANY_SUBJECT_CLAIM"
ANY_GITHUB_REPO = "ANY_GITHUB_REPO"
ANY_GITHUB_ORG = "ANY_GITHUB_ORG"
ANY_DEPLOYMENT_BRANCH = "ANY_DEPLOYMENT_BRANCH"
ANY_OIDC_PHYSICAL_RESOURCE_ID = "ANY_OIDC_PHYSICAL_RESOURCE_ID"


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
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_did_user_provide_all_required_resources_returns_false_if_the_stage_was_initialized_without_any_of_the_resources_even_if_fulfilled_after_bootstrap(
        self, update_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        # setup
        stack_output = Mock()
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stack_output.get.return_value = ANY_ARN
        update_stack_mock.return_value = stack_output
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
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    @patch.object(Stage, "did_user_provide_all_required_resources")
    def test_bootstrap_will_not_deploy_the_cfn_template_if_all_resources_are_already_provided(
        self, did_user_provide_all_required_resources_mock, update_stack_mock, click_mock
    ):
        did_user_provide_all_required_resources_mock.return_value = True
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=False)
        update_stack_mock.assert_not_called()

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_bootstrap_will_confirm_before_deploying_unless_confirm_changeset_is_disabled(
        self, update_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        click_mock.confirm.return_value = False
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=False)
        click_mock.confirm.assert_not_called()
        update_stack_mock.assert_called_once()
        update_stack_mock.reset_mock()
        stage.bootstrap(confirm_changeset=True)
        click_mock.confirm.assert_called_once()
        update_stack_mock.assert_not_called()  # As the user choose to not confirm

    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_bootstrap_will_not_deploy_the_cfn_template_if_the_user_did_not_confirm(
        self, update_stack_mock, click_mock
    ):
        click_mock.confirm.return_value = False
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=True)
        update_stack_mock.assert_not_called()

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_bootstrap_will_deploy_the_cfn_template_if_the_user_did_confirm(
        self, update_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        click_mock.confirm.return_value = True
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stage: Stage = Stage(name=ANY_STAGE_CONFIGURATION_NAME)
        stage.bootstrap(confirm_changeset=True)
        update_stack_mock.assert_called_once()

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_bootstrap_will_pass_arns_of_all_user_provided_resources_any_empty_strings_for_other_resources_to_the_cfn_stack(
        self, update_stack_mock, click_mock, pipeline_user_secret_pair_mock
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
        update_stack_mock.assert_called_once()
        args, kwargs = update_stack_mock.call_args_list[0]
        expected_parameter_overrides = {
            "PipelineUserArn": ANY_PIPELINE_USER_ARN,
            "PipelineExecutionRoleArn": "",
            "CloudFormationExecutionRoleArn": "",
            "ArtifactsBucketArn": ANY_ARTIFACTS_BUCKET_ARN,
            "CreateImageRepository": "true",
            "ImageRepositoryArn": ANY_IMAGE_REPOSITORY_ARN,
            "UseOidcProvider": "false",
            "CreateNewOidcProvider": "false",
            "IdentityProviderThumbprint": "",
            "OidcClientId": "",
            "OidcProviderUrl": "",
            "SubjectClaim": "",
            "UseOidcProvider": "false",
        }
        self.assertEqual(expected_parameter_overrides, kwargs["parameter_overrides"])

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage._get_pipeline_user_secret_pair")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_bootstrap_will_fullfill_all_resource_arns(
        self, update_stack_mock, click_mock, pipeline_user_secret_pair_mock
    ):
        # setup
        pipeline_user_secret_pair_mock.return_value = ("id", "secret")
        stack_output = Mock()
        stack_output.get.return_value = ANY_ARN
        update_stack_mock.return_value = stack_output
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
        update_stack_mock.assert_called_once()
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
        expected_calls.append(
            call(cmd_names=cmd_names, section="parameters", key="permissions_provider", value="AWS IAM")
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

    @patch("samcli.lib.pipeline.bootstrap.stage.crypto")
    @patch("samcli.lib.pipeline.bootstrap.stage.socket")
    @patch("samcli.lib.pipeline.bootstrap.stage.SSL")
    @patch("samcli.lib.pipeline.bootstrap.stage.requests")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    def test_generate_oidc_provider_thumbprint(self, click_mock, requests_mock, ssl_mock, socket_mock, crypto_mock):
        # setup
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
        )
        response_mock = Mock(requests.Response)
        requests_mock.get.return_value = response_mock
        response_mock.json.return_value = {"jwks_uri": "https://server.example.com/test"}
        connection_mock = Mock(OpenSSL.SSL.Connection)
        ssl_mock.Connection.return_value = connection_mock
        certificate_mock = Mock(OpenSSL.crypto.x509)
        connection_mock.get_peer_cert_chain.return_value = [certificate_mock]
        dumped_certificate = "not a real certificate object dump".encode("utf-8")
        crypto_mock.dump_certificate.return_value = dumped_certificate
        expected_thumbprint = hashlib.sha1(dumped_certificate).hexdigest()

        # trigger
        actual_thumbprint = stage.generate_thumbprint("https://server.example.com")

        # verify
        self.assertEqual(expected_thumbprint, actual_thumbprint)

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage.generate_thumbprint")
    @patch("samcli.lib.pipeline.bootstrap.stage.boto3")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_creates_new_oidc_provider_if_needed(
        self, update_stack_mock, click_mock, boto3_mock, generate_thumbprint_mock
    ):

        # setup
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            permissions_provider="oidc",
            oidc_provider_url=ANY_OIDC_PROVIDER_URL,
            oidc_client_id=ANY_OIDC_CLIENT_ID,
            subject_claim=ANY_SUBJECT_CLAIM,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=False,
        )
        stack_output = Mock()
        stack_output.get.return_value = ANY_ARN
        update_stack_mock.return_value = stack_output
        client_mock = Mock()
        boto3_mock.client.return_value = client_mock
        open_id_connect_providers_mock = {"OpenIDConnectProviderList": [{"Arn": ANY_ARN}]}
        client_mock.list_open_id_connect_providers.return_value = open_id_connect_providers_mock

        self.assertFalse(stage.create_new_oidc_provider)

        # trigger
        stage.bootstrap(confirm_changeset=False)

        # verify
        self.assertTrue(stage.create_new_oidc_provider)

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage.generate_thumbprint")
    @patch("samcli.lib.pipeline.bootstrap.stage.boto3")
    @patch("samcli.lib.pipeline.bootstrap.stage.click")
    @patch("samcli.lib.pipeline.bootstrap.stage.update_stack")
    def test_doesnt_create_new_oidc_provider(self, update_stack_mock, click_mock, boto3_mock, generate_thumbprint_mock):

        # setup
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            permissions_provider="oidc",
            oidc_provider_url=ANY_OIDC_PROVIDER_URL,
            oidc_client_id=ANY_OIDC_CLIENT_ID,
            subject_claim=ANY_SUBJECT_CLAIM,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=False,
        )
        stack_output = Mock()
        stack_output.get.return_value = ANY_ARN
        update_stack_mock.return_value = stack_output
        client_mock = Mock()
        session_mock = Mock()
        boto3_mock.Session.return_value = session_mock
        session_mock.client.return_value = client_mock
        open_id_connect_providers_mock = {"OpenIDConnectProviderList": [{"Arn": ANY_OIDC_PROVIDER_URL}]}
        stack_detail_mock = {"StackResourceDetail": {"PhysicalResourceId": ANY_OIDC_PHYSICAL_RESOURCE_ID}}
        client_mock.list_open_id_connect_providers.return_value = open_id_connect_providers_mock
        client_mock.describe_stack_resource.return_value = stack_detail_mock

        # trigger
        stage.bootstrap(confirm_changeset=False)

        # verify
        self.assertFalse(stage.create_new_oidc_provider)

    @patch("samcli.lib.pipeline.bootstrap.stage.boto3")
    def test_should_create_new_oidc_provider_returns_true_if_no_url(self, boto3_mock):

        # setup
        stage: Stage = Stage(
            name=ANY_STAGE_CONFIGURATION_NAME,
            permissions_provider="oidc",
            oidc_provider_url="",
            oidc_client_id=ANY_OIDC_CLIENT_ID,
            subject_claim=ANY_SUBJECT_CLAIM,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=False,
        )
        client_mock = Mock()
        boto3_mock.client.return_value = client_mock
        open_id_connect_providers_mock = {"OpenIDConnectProviderList": [{"Arn": ANY_OIDC_PROVIDER_URL}]}
        client_mock.list_open_id_connect_providers.return_value = open_id_connect_providers_mock
        stack_detail_mock = {"StackResourceDetail": {"PhysicalResourceId": ANY_OIDC_PHYSICAL_RESOURCE_ID}}
        client_mock.describe_stack_resource.return_value = stack_detail_mock

        # trigger
        result = stage._should_create_new_provider("random_stack_name")

        # verify
        self.assertFalse(result)

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


class TestSSLContext(TestCase):
    def test_return_ctx(self):
        ctx = _get_secure_ssl_context()
        self.assertIsInstance(ctx, OpenSSL.SSL.Context)

    @patch("samcli.lib.pipeline.bootstrap.stage.SSL.Context")
    def test_options_set(self, SSLContext_mock):
        context_mock = Mock()
        SSLContext_mock.return_value = context_mock
        ctx = _get_secure_ssl_context()
        SSLContext_mock.assert_called_with(OpenSSL.SSL.TLS_METHOD)

        # NOTE (hawflau): do not remove any of below as they are insecure versions
        context_mock.set_options.assert_any_call(OpenSSL.SSL.OP_NO_TLSv1)
        context_mock.set_options.assert_any_call(OpenSSL.SSL.OP_NO_TLSv1_1)
        context_mock.set_options.assert_any_call(OpenSSL.SSL.OP_NO_SSLv2)
        context_mock.set_options.assert_any_call(OpenSSL.SSL.OP_NO_SSLv3)
