from unittest import TestCase
from unittest.mock import patch, Mock

import click
from click.testing import CliRunner

from samcli.commands.pipeline.bootstrap.cli import (
    _load_saved_pipeline_user_arn,
    _get_bootstrap_command_names,
    PIPELINE_CONFIG_FILENAME,
    PIPELINE_CONFIG_DIR,
)
from samcli.commands.pipeline.bootstrap.cli import cli as bootstrap_cmd
from samcli.commands.pipeline.bootstrap.cli import do_cli as bootstrap_cli

ANY_REGION = "ANY_REGION"
ANY_PROFILE = "ANY_PROFILE"
ANY_STAGE_CONFIGURATION_NAME = "ANY_STAGE_CONFIGURATION_NAME"
ANY_PIPELINE_USER_ARN = "ANY_PIPELINE_USER_ARN"
ANY_PIPELINE_EXECUTION_ROLE_ARN = "ANY_PIPELINE_EXECUTION_ROLE_ARN"
ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN = "ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN"
ANY_ARTIFACTS_BUCKET_ARN = "ANY_ARTIFACTS_BUCKET_ARN"
ANY_IMAGE_REPOSITORY_ARN = "ANY_IMAGE_REPOSITORY_ARN"
ANY_ARN = "ANY_ARN"
ANY_CONFIG_FILE = "ANY_CONFIG_FILE"
ANY_CONFIG_ENV = "ANY_CONFIG_ENV"
PIPELINE_BOOTSTRAP_COMMAND_NAMES = ["pipeline", "bootstrap"]


class TestCli(TestCase):
    def setUp(self) -> None:
        self.cli_context = {
            "region": ANY_REGION,
            "profile": ANY_PROFILE,
            "interactive": True,
            "stage_configuration_name": ANY_STAGE_CONFIGURATION_NAME,
            "pipeline_user_arn": ANY_PIPELINE_USER_ARN,
            "pipeline_execution_role_arn": ANY_PIPELINE_EXECUTION_ROLE_ARN,
            "cloudformation_execution_role_arn": ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            "artifacts_bucket_arn": ANY_ARTIFACTS_BUCKET_ARN,
            "create_image_repository": True,
            "image_repository_arn": ANY_IMAGE_REPOSITORY_ARN,
            "confirm_changeset": True,
            "config_file": ANY_CONFIG_FILE,
            "config_env": ANY_CONFIG_ENV,
        }

    @patch("samcli.commands.pipeline.bootstrap.cli.do_cli")
    def test_bootstrap_command_default_argument_values(self, do_cli_mock):
        runner: CliRunner = CliRunner()
        runner.invoke(bootstrap_cmd)
        # Test the defaults are as following:
        # interactive -> True
        # create_image_repository -> False
        # confirm_changeset -> True
        # region, profile, stage_configuration_name and all ARNs are None
        do_cli_mock.assert_called_once_with(
            region=None,
            profile=None,
            interactive=True,
            stage_configuration_name=None,
            pipeline_user_arn=None,
            pipeline_execution_role_arn=None,
            cloudformation_execution_role_arn=None,
            artifacts_bucket_arn=None,
            create_image_repository=False,
            image_repository_arn=None,
            confirm_changeset=True,
            config_file="default",
            config_env="samconfig.toml",
        )

    @patch("samcli.commands.pipeline.bootstrap.cli.do_cli")
    def test_bootstrap_command_flag_arguments(self, do_cli_mock):
        runner: CliRunner = CliRunner()
        runner.invoke(bootstrap_cmd, args=["--interactive", "--no-create-image-repository", "--confirm-changeset"])
        args, kwargs = do_cli_mock.call_args
        self.assertTrue(kwargs["interactive"])
        self.assertFalse(kwargs["create_image_repository"])
        self.assertTrue(kwargs["confirm_changeset"])

        runner.invoke(bootstrap_cmd, args=["--no-interactive", "--create-image-repository", "--no-confirm-changeset"])
        args, kwargs = do_cli_mock.call_args
        self.assertFalse(kwargs["interactive"])
        self.assertTrue(kwargs["create_image_repository"])
        self.assertFalse(kwargs["confirm_changeset"])

    @patch("samcli.commands.pipeline.bootstrap.cli.do_cli")
    def test_bootstrap_command_with_different_arguments_combination(self, do_cli_mock):
        runner: CliRunner = CliRunner()
        runner.invoke(
            bootstrap_cmd,
            args=["--no-interactive", "--stage", "environment1", "--bucket", "bucketARN"],
        )
        args, kwargs = do_cli_mock.call_args
        self.assertFalse(kwargs["interactive"])
        self.assertEqual(kwargs["stage_configuration_name"], "environment1")
        self.assertEqual(kwargs["artifacts_bucket_arn"], "bucketARN")

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_saved_pipeline_user_arn")
    @patch("samcli.commands.pipeline.bootstrap.cli.Stage")
    @patch("samcli.commands.pipeline.bootstrap.cli.GuidedContext")
    def test_bootstrapping_normal_interactive_flow(
        self, guided_context_mock, environment_mock, load_saved_pipeline_user_arn_mock, get_command_names_mock
    ):
        # setup
        gc_instance = Mock()
        guided_context_mock.return_value = gc_instance
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        load_saved_pipeline_user_arn_mock.return_value = ANY_PIPELINE_USER_ARN
        self.cli_context["interactive"] = True
        self.cli_context["pipeline_user_arn"] = None
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES

        # trigger
        bootstrap_cli(**self.cli_context)

        # verify
        load_saved_pipeline_user_arn_mock.assert_called_once()
        gc_instance.run.assert_called_once()
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=True)
        environment_instance.print_resources_summary.assert_called_once()
        environment_instance.save_config_safe.assert_called_once_with(
            config_dir=PIPELINE_CONFIG_DIR,
            filename=PIPELINE_CONFIG_FILENAME,
            cmd_names=PIPELINE_BOOTSTRAP_COMMAND_NAMES,
        )

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_saved_pipeline_user_arn")
    @patch("samcli.commands.pipeline.bootstrap.cli.Stage")
    @patch("samcli.commands.pipeline.bootstrap.cli.GuidedContext")
    def test_bootstrap_will_not_try_loading_pipeline_user_if_already_provided(
        self, guided_context_mock, environment_mock, load_saved_pipeline_user_arn_mock, get_command_names_mock
    ):
        bootstrap_cli(**self.cli_context)
        load_saved_pipeline_user_arn_mock.assert_not_called()

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_saved_pipeline_user_arn")
    @patch("samcli.commands.pipeline.bootstrap.cli.Stage")
    @patch("samcli.commands.pipeline.bootstrap.cli.GuidedContext")
    def test_bootstrap_will_try_loading_pipeline_user_if_not_provided(
        self, guided_context_mock, environment_mock, load_saved_pipeline_user_arn_mock, get_command_names_mock
    ):
        self.cli_context["pipeline_user_arn"] = None
        bootstrap_cli(**self.cli_context)
        load_saved_pipeline_user_arn_mock.assert_called_once()

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_saved_pipeline_user_arn")
    @patch("samcli.commands.pipeline.bootstrap.cli.Stage")
    @patch("samcli.commands.pipeline.bootstrap.cli.GuidedContext")
    def test_stage_configuration_name_is_required_to_be_provided_in_case_of_non_interactive_mode(
        self, guided_context_mock, environment_mock, load_saved_pipeline_user_arn_mock, get_command_names_mock
    ):
        self.cli_context["interactive"] = False
        self.cli_context["stage_configuration_name"] = None
        with self.assertRaises(click.UsageError):
            bootstrap_cli(**self.cli_context)

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_saved_pipeline_user_arn")
    @patch("samcli.commands.pipeline.bootstrap.cli.Stage")
    @patch("samcli.commands.pipeline.bootstrap.cli.GuidedContext")
    def test_stage_configuration_name_is_not_required_to_be_provided_in_case_of_interactive_mode(
        self, guided_context_mock, environment_mock, load_saved_pipeline_user_arn_mock, get_command_names_mock
    ):
        self.cli_context["interactive"] = True
        self.cli_context["stage_configuration_name"] = None
        bootstrap_cli(**self.cli_context)  # No exception is thrown

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_saved_pipeline_user_arn")
    @patch("samcli.commands.pipeline.bootstrap.cli.Stage")
    @patch("samcli.commands.pipeline.bootstrap.cli.GuidedContext")
    def test_guided_context_will_be_enabled_or_disabled_based_on_the_interactive_mode(
        self, guided_context_mock, environment_mock, load_saved_pipeline_user_arn_mock, get_command_names_mock
    ):
        gc_instance = Mock()
        guided_context_mock.return_value = gc_instance
        self.cli_context["interactive"] = False
        bootstrap_cli(**self.cli_context)
        gc_instance.run.assert_not_called()
        self.cli_context["interactive"] = True
        bootstrap_cli(**self.cli_context)
        gc_instance.run.assert_called_once()

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_saved_pipeline_user_arn")
    @patch("samcli.commands.pipeline.bootstrap.cli.Stage")
    @patch("samcli.commands.pipeline.bootstrap.cli.GuidedContext")
    def test_bootstrapping_will_confirm_before_creating_the_resources_unless_the_user_choose_not_to(
        self, guided_context_mock, environment_mock, load_saved_pipeline_user_arn_mock, get_command_names_mock
    ):
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["confirm_changeset"] = False
        bootstrap_cli(**self.cli_context)
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=False)
        environment_instance.bootstrap.reset_mock()
        self.cli_context["confirm_changeset"] = True
        bootstrap_cli(**self.cli_context)
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=True)

    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_saved_pipeline_user_arn_will_read_from_the_correct_file(
        self, get_command_names_mock, sam_config_mock
    ):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = False

        # trigger
        _load_saved_pipeline_user_arn()

        # verify
        sam_config_mock.assert_called_once_with(config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME)

    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_saved_pipeline_user_arn_will_return_non_if_the_pipeline_toml_file_is_not_found(
        self, get_command_names_mock, sam_config_mock
    ):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = False

        # trigger
        pipeline_user_arn = _load_saved_pipeline_user_arn()

        # verify
        self.assertIsNone(pipeline_user_arn)

    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_saved_pipeline_user_arn_will_return_non_if_the_pipeline_toml_file_does_not_contain_pipeline_user(
        self, get_command_names_mock, sam_config_mock
    ):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = True
        sam_config_instance_mock.get_all.return_value = {"non-pipeline_user-key": "any_value"}

        # trigger
        pipeline_user_arn = _load_saved_pipeline_user_arn()

        # verify
        self.assertIsNone(pipeline_user_arn)

    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_saved_pipeline_user_arn_returns_the_pipeline_user_arn_from_the_pipeline_toml_file(
        self, get_command_names_mock, sam_config_mock
    ):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = True
        sam_config_instance_mock.get_all.return_value = {"pipeline_user": ANY_PIPELINE_USER_ARN}

        # trigger
        pipeline_user_arn = _load_saved_pipeline_user_arn()

        # verify
        self.assertEqual(pipeline_user_arn, ANY_PIPELINE_USER_ARN)
