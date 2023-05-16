from unittest import TestCase
from unittest.mock import patch, Mock
from parameterized import parameterized

import click
from click.testing import CliRunner

from samcli.commands.pipeline.bootstrap.cli import (
    _load_config_values,
    PIPELINE_CONFIG_FILENAME,
    PIPELINE_CONFIG_DIR,
)
from samcli.commands.pipeline.bootstrap.cli import cli as bootstrap_cmd
from samcli.commands.pipeline.bootstrap.cli import do_cli as bootstrap_cli
from samcli.commands.pipeline.bootstrap.guided_context import BITBUCKET, GITHUB_ACTIONS, GITLAB
from samcli.commands.pipeline.bootstrap.oidc_config import (
    GitHubOidcConfig,
    OidcConfig,
    GitLabOidcConfig,
    BitbucketOidcConfig,
)

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
ANY_CICD_PROVIDER = "ANY_CICD_PROVIDER"
ANY_OIDC_PROVIDER_URL = "ANY_OIDC_PROVIDER_URL"
ANY_OIDC_CLIENT_ID = "ANY_OIDC_CLIENT_ID"
ANY_OIDC_PROVIDER = "ANY_OIDC_PROVIDER"
ANY_GITHUB_ORG = "ANY_GITHUB_ORG"
ANY_GITHUB_REPO = "ANY_GITHUB_REPO"
ANY_DEPLOYMENT_BRANCH = "ANY_DEPLOYMENT_BRANCH"
ANY_GITLAB_PROJECT = "ANY_GITLAB_PROJECT"
ANY_GITLAB_GROUP = "ANY_GITLAB_GROUP"
ANY_BITBUCKET_REPO_UUID = "ANY_BITBUCKET_REPO_UUID"
ANY_SUBJECT_CLAIM = "ANY_SUBJECT_CLAIM"
ANY_BUILT_SUBJECT_CLAIM = "repo:ANY_GITHUB_ORG/ANY_GITHUB_REPO:ref:refs/heads/ANY_DEPLOYMENT_BRANCH"
ANY_BUILT_GITLAB_SUBJECT_CLAIM = (
    "project_path:ANY_GITLAB_GROUP/ANY_GITLAB_PROJECT:ref_type:branch:ref" ":ANY_DEPLOYMENT_BRANCH"
)
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
            "permissions_provider": "iam",
            "oidc_provider_url": ANY_OIDC_PROVIDER_URL,
            "oidc_client_id": ANY_OIDC_CLIENT_ID,
            "oidc_provider": GITHUB_ACTIONS,
            "github_org": None,
            "github_repo": None,
            "gitlab_project": None,
            "gitlab_group": None,
            "bitbucket_repo_uuid": None,
            "deployment_branch": ANY_DEPLOYMENT_BRANCH,
            "cicd_provider": ANY_CICD_PROVIDER,
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
            permissions_provider="iam",
            oidc_provider_url=None,
            oidc_client_id=None,
            github_org=None,
            github_repo=None,
            deployment_branch=None,
            oidc_provider=None,
            gitlab_group=None,
            gitlab_project=None,
            bitbucket_repo_uuid=None,
            cicd_provider=None,
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
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrapping_normal_interactive_flow(self, guided_context_mock, environment_mock, get_command_names_mock):
        # setup
        gc_instance = Mock()
        gc_instance.permissions_provider = "iam"
        guided_context_mock.return_value = gc_instance
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["interactive"] = True
        self.cli_context["pipeline_user_arn"] = None
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES

        # trigger
        bootstrap_cli(**self.cli_context)

        # verify
        gc_instance.run.assert_called_once()
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=True)
        environment_instance.print_resources_summary.assert_called_once()
        environment_instance.save_config_safe.assert_called_once_with(
            config_dir=PIPELINE_CONFIG_DIR,
            filename=PIPELINE_CONFIG_FILENAME,
            cmd_names=PIPELINE_BOOTSTRAP_COMMAND_NAMES,
        )

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    def test_bootstrapping_oidc_non_interactive_fails_if_missing_parameters(self, environment_mock):
        # setup
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["interactive"] = False
        self.cli_context["permissions_provider"] = "oidc"
        self.cli_context["oidc_provider_url"] = None
        self.cli_context["oidc_client_id"] = None
        self.cli_context["oidc_provider"] = None

        # trigger
        with self.assertRaises(click.UsageError):
            bootstrap_cli(**self.cli_context)

        # verify
        environment_instance.bootstrap.assert_not_called()
        environment_instance.print_resources_summary.assert_not_called()
        environment_instance.save_config_safe.assert_not_called()

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    def test_bootstrapping_oidc_non_interactive_fails_if_missing_github_parameters(self, environment_mock):
        # setup
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["interactive"] = False
        self.cli_context["permissions_provider"] = "oidc"
        self.cli_context["oidc_provider"] = GITHUB_ACTIONS
        self.cli_context["github_org"] = None
        self.cli_context["github_repo"] = None
        self.cli_context["deployment_branch"] = None

        # trigger
        with self.assertRaises(click.UsageError):
            bootstrap_cli(**self.cli_context)

        # verify
        environment_instance.bootstrap.assert_not_called()
        environment_instance.print_resources_summary.assert_not_called()
        environment_instance.save_config_safe.assert_not_called()

    @parameterized.expand(
        [
            ("any_github_org", None, "any_gitlab_group", None, None),
            (None, "any_github_repo", None, "any_gitlab_project", None),
            (None, "any_github_repo", None, None, "bitbucket_repo_uuid"),
            (None, None, None, "any_gitlab_group", "bitbucket_repo_uuid"),
        ]
    )
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    def test_bootstrapping_oidc_fails_conflict_parameters(
        self, github_org, github_repo, gitlab_group, gitlab_project, bitbucket_repo_uuid, environment_mock
    ):
        # setup
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["interactive"] = False
        self.cli_context["permissions_provider"] = "oidc"
        self.cli_context["oidc_provider"] = GITHUB_ACTIONS
        self.cli_context["github_org"] = github_org
        self.cli_context["github_repo"] = github_repo
        self.cli_context["gitlab_group"] = gitlab_group
        self.cli_context["gitlab_project"] = gitlab_project
        self.cli_context["bitbucket_repo_uuid"] = bitbucket_repo_uuid
        self.cli_context["deployment_branch"] = None

        # trigger
        with self.assertRaises(click.UsageError):
            bootstrap_cli(**self.cli_context)

        # verify
        environment_instance.bootstrap.assert_not_called()
        environment_instance.print_resources_summary.assert_not_called()
        environment_instance.save_config_safe.assert_not_called()

    @patch("samcli.commands.pipeline.bootstrap.pipeline_oidc_provider")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrapping_oidc_interactive_flow(
        self,
        guided_context_mock,
        environment_mock,
        get_command_names_mock,
        pipeline_provider_mock,
    ):
        # setup
        gc_instance = Mock()
        gc_instance.permissions_provider = "oidc"
        guided_context_mock.return_value = gc_instance
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["interactive"] = True
        self.cli_context["permissions_provider"] = "oidc"
        self.cli_context["github_org"] = ANY_GITHUB_ORG
        self.cli_context["github_repo"] = ANY_GITHUB_REPO
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES

        # trigger
        bootstrap_cli(**self.cli_context)

        # verify
        gc_instance.run.assert_called_once()
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=True)
        environment_instance.print_resources_summary.assert_called_once()
        environment_instance.save_config_safe.assert_called_once_with(
            config_dir=PIPELINE_CONFIG_DIR,
            filename=PIPELINE_CONFIG_FILENAME,
            cmd_names=PIPELINE_BOOTSTRAP_COMMAND_NAMES,
        )

    @patch("samcli.commands.pipeline.bootstrap.pipeline_oidc_provider")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrapping_oidc_interactive_flow_gitlab(
        self,
        guided_context_mock,
        environment_mock,
        get_command_names_mock,
        pipeline_provider_mock,
    ):
        # setup
        gc_instance = Mock()
        gc_instance.permissions_provider = "oidc"
        guided_context_mock.return_value = gc_instance
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["interactive"] = True
        self.cli_context["permissions_provider"] = "oidc"
        self.cli_context["oidc_provider"] = GITLAB
        self.cli_context["gitlab_group"] = ANY_GITLAB_GROUP
        self.cli_context["gitlab_project"] = ANY_GITLAB_PROJECT
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES

        # trigger
        bootstrap_cli(**self.cli_context)

        # verify
        gc_instance.run.assert_called_once()
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=True)
        environment_instance.print_resources_summary.assert_called_once()
        environment_instance.save_config_safe.assert_called_once_with(
            config_dir=PIPELINE_CONFIG_DIR,
            filename=PIPELINE_CONFIG_FILENAME,
            cmd_names=PIPELINE_BOOTSTRAP_COMMAND_NAMES,
        )

    @patch("samcli.commands.pipeline.bootstrap.pipeline_oidc_provider")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrapping_oidc_interactive_flow_bitbucket(
        self,
        guided_context_mock,
        environment_mock,
        get_command_names_mock,
        pipeline_provider_mock,
    ):
        # setup
        gc_instance = Mock()
        gc_instance.permissions_provider = "oidc"
        guided_context_mock.return_value = gc_instance
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        self.cli_context["interactive"] = True
        self.cli_context["permissions_provider"] = "oidc"
        self.cli_context["oidc_provider"] = BITBUCKET
        self.cli_context["bitbucket_repo_uuid"] = ANY_BITBUCKET_REPO_UUID
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES

        # trigger
        bootstrap_cli(**self.cli_context)

        # verify
        gc_instance.run.assert_called_once()
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=True)
        environment_instance.print_resources_summary.assert_called_once()
        environment_instance.save_config_safe.assert_called_once_with(
            config_dir=PIPELINE_CONFIG_DIR,
            filename=PIPELINE_CONFIG_FILENAME,
            cmd_names=PIPELINE_BOOTSTRAP_COMMAND_NAMES,
        )

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_config_values")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrap_will_try_loading_pipeline_user_if_not_provided(
        self, guided_context_mock, environment_mock, load_config_values_mock, get_command_names_mock
    ):
        self.cli_context["pipeline_user_arn"] = None
        bootstrap_cli(**self.cli_context)
        load_config_values_mock.assert_called_once()

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_config_values")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrap_will_try_loading_oidc_values_if_not_provided(
        self, guided_context_mock, environment_mock, load_saved_oidc_values_arn_mock, get_command_names_mock
    ):
        self.cli_context["oidc_provider"] = None
        bootstrap_cli(**self.cli_context)
        load_saved_oidc_values_arn_mock.assert_called_once()

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_config_values")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_stage_configuration_name_is_required_to_be_provided_in_case_of_non_interactive_mode(
        self, guided_context_mock, environment_mock, load_config_values_mock, get_command_names_mock
    ):
        self.cli_context["interactive"] = False
        self.cli_context["stage_configuration_name"] = None
        with self.assertRaises(click.UsageError):
            bootstrap_cli(**self.cli_context)

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_config_values")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_stage_configuration_name_is_not_required_to_be_provided_in_case_of_interactive_mode(
        self, guided_context_mock, environment_mock, load_config_values_mock, get_command_names_mock
    ):
        self.cli_context["interactive"] = True
        self.cli_context["stage_configuration_name"] = None
        bootstrap_cli(**self.cli_context)  # No exception is thrown

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_config_values")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_guided_context_will_be_enabled_or_disabled_based_on_the_interactive_mode(
        self, guided_context_mock, environment_mock, load_config_values_mock, get_command_names_mock
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
    @patch("samcli.commands.pipeline.bootstrap.cli._load_config_values")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrapping_will_confirm_before_creating_the_resources_unless_the_user_choose_not_to(
        self, guided_context_mock, environment_mock, load_config_values_mock, get_command_names_mock
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
    def test_load_config_values_will_read_from_the_correct_file(self, get_command_names_mock, sam_config_mock):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = False

        # trigger
        _load_config_values()

        # verify
        sam_config_mock.assert_called_once_with(config_dir=PIPELINE_CONFIG_DIR, filename=PIPELINE_CONFIG_FILENAME)

    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_config_values_will_return_non_if_the_pipeline_toml_file_is_not_found(
        self, get_command_names_mock, sam_config_mock
    ):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = False

        # trigger
        config_values = _load_config_values()

        # verify
        self.assertEqual(config_values, {})

    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_config_values_will_return_no_pipeline_user_if_the_pipeline_toml_file_does_not_contain_pipeline_user(
        self, get_command_names_mock, sam_config_mock
    ):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = True
        sam_config_instance_mock.get_all.return_value = {"non-pipeline_user-key": "any_value"}

        # trigger
        pipeline_user_arn = _load_config_values().get("pipeline_user")

        # verify
        self.assertIsNone(pipeline_user_arn)

    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_config_values_works_from_the_pipeline_toml_file(self, get_command_names_mock, sam_config_mock):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = True
        sam_config_instance_mock.get_all.return_value = {"pipeline_user": ANY_PIPELINE_USER_ARN}

        # trigger
        config_values = _load_config_values()

        # verify
        self.assertEqual(config_values, {"pipeline_user": ANY_PIPELINE_USER_ARN})

    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    @patch("samcli.commands.pipeline.bootstrap.cli.SamConfig")
    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    def test_load_saved_oidc_values_returns_values_from_file(
        self, get_command_names_mock, sam_config_mock, guided_context_mock, stage_mock
    ):
        # setup
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES
        sam_config_instance_mock = Mock()
        sam_config_mock.return_value = sam_config_instance_mock
        sam_config_instance_mock.exists.return_value = True
        sam_config_instance_mock.get_all.return_value = {
            "oidc_provider_url": "saved_url",
            "oidc_provider": "saved_provider",
            "oidc_client_id": "saved_client_id",
            "github_org": "saved_org",
            "github_repo": "saved_repo",
            "deployment_branch": "saved_branch",
            "permissions_provider": "OpenID Connect (OIDC)",
        }
        self.cli_context["github_org"] = ANY_GITHUB_ORG
        self.cli_context["github_repo"] = ANY_GITHUB_REPO
        github_config = GitHubOidcConfig(
            github_repo="saved_repo", github_org="saved_org", deployment_branch="saved_branch"
        )
        oidc_config = OidcConfig(
            oidc_provider="saved_provider", oidc_client_id="saved_client_id", oidc_provider_url="saved_url"
        )
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch="saved_branch")
        bitbucket_config = BitbucketOidcConfig(None)
        # trigger
        bootstrap_cli(**self.cli_context)

        # verify
        guided_context_mock.assert_called_with(
            github_config=github_config,
            gitlab_config=gitlab_config,
            oidc_config=oidc_config,
            bitbucket_config=bitbucket_config,
            permissions_provider="oidc",
            profile=ANY_PROFILE,
            stage_configuration_name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
            region=ANY_REGION,
            enable_oidc_option=False,
        )

    @patch("samcli.commands.pipeline.bootstrap.cli._get_bootstrap_command_names")
    @patch("samcli.commands.pipeline.bootstrap.cli._load_config_values")
    @patch("samcli.lib.pipeline.bootstrap.stage.Stage")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext")
    def test_bootstrapping_normal_interactive_flow_with_non_user_provided_user(
        self, guided_context_mock, environment_mock, load_config_values_mock, get_command_names_mock
    ):
        # setup
        gc_instance = Mock()
        gc_instance.permissions_provider = "iam"
        guided_context_mock.return_value = gc_instance
        environment_instance = Mock()
        environment_mock.return_value = environment_instance
        environment_instance.permissions_provider = "iam"
        load_config_values_mock.return_value = {"pipeline_user": ANY_PIPELINE_USER_ARN}
        environment_instance.pipeline_user.is_user_provided = False
        self.cli_context["interactive"] = True
        self.cli_context["pipeline_user_arn"] = None
        get_command_names_mock.return_value = PIPELINE_BOOTSTRAP_COMMAND_NAMES

        # trigger
        bootstrap_cli(**self.cli_context)

        # verify
        load_config_values_mock.assert_called_once()
        gc_instance.run.assert_called_once()
        environment_instance.bootstrap.assert_called_once_with(confirm_changeset=True)
        environment_instance.print_resources_summary.assert_called_once()
        environment_instance.save_config_safe.assert_called_once_with(
            config_dir=PIPELINE_CONFIG_DIR,
            filename=PIPELINE_CONFIG_FILENAME,
            cmd_names=PIPELINE_BOOTSTRAP_COMMAND_NAMES,
        )
