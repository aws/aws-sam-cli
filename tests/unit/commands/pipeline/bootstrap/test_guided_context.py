from unittest import TestCase
from unittest.mock import patch, Mock, ANY

from parameterized import parameterized

from samcli.commands.pipeline.bootstrap.guided_context import IAM, GuidedContext, GITHUB_ACTIONS
from samcli.commands.pipeline.bootstrap.oidc_config import (
    GitHubOidcConfig,
    BitbucketOidcConfig,
    GitLabOidcConfig,
    OidcConfig,
)

ANY_STAGE_CONFIGURATION_NAME = "ANY_STAGE_CONFIGURATION_NAME"
ANY_PIPELINE_USER_ARN = "ANY_PIPELINE_USER_ARN"
ANY_PIPELINE_EXECUTION_ROLE_ARN = "ANY_PIPELINE_EXECUTION_ROLE_ARN"
ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN = "ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN"
ANY_ARTIFACTS_BUCKET_ARN = "ANY_ARTIFACTS_BUCKET_ARN"
ANY_IMAGE_REPOSITORY_ARN = "ANY_IMAGE_REPOSITORY_ARN"
ANY_ARN = "ANY_ARN"
ANY_REGION = "us-east-2"
ANY_OIDC_PROVIDER = GITHUB_ACTIONS
ANY_OIDC_PROVIDER_URL = "https://ANY_OIDC_PROVIDER.com"
ANY_OIDC_CLIENT_ID = "ANY_OIDC_CLIENT_ID"
ANY_GITHUB_ORG = "ANY_GITHUB_ORG"
ANY_GITHUB_REPO = "ANY_GITHUB_REPO"
ANY_GITLAB_GROUP = "ANY_GITLAB_GROUP"
ANY_GITLAB_PROJECT = "ANY_GITLAB_PROJECT"
ANY_DEPLOYMENT_BRANCH = "ANY_DEPLOYMENT_BRANCH"
ANY_BITBUCKET_REPO_UUID = "ANY_BITBUCKET_REPO_UUID"


class TestGuidedContext(TestCase):
    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_not_prompt_for_fields_that_are_already_provided(
        self, prompt_account_id_mock, click_mock, account_id_mock
    ):
        account_id_mock.return_value = "1234567890"
        click_mock.confirm.return_value = False
        click_mock.prompt = Mock(return_value="0")
        github_config = GitHubOidcConfig(
            github_org=ANY_GITHUB_ORG, github_repo=ANY_GITHUB_REPO, deployment_branch=ANY_DEPLOYMENT_BRANCH
        )
        gitlab_config = GitLabOidcConfig(
            gitlab_group=ANY_GITLAB_GROUP, gitlab_project=ANY_GITLAB_PROJECT, deployment_branch=ANY_DEPLOYMENT_BRANCH
        )
        bitbucket_config = BitbucketOidcConfig(ANY_BITBUCKET_REPO_UUID)
        oidc_config = OidcConfig(
            oidc_provider=ANY_OIDC_PROVIDER, oidc_provider_url=ANY_OIDC_PROVIDER_URL, oidc_client_id=ANY_OIDC_CLIENT_ID
        )
        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            stage_configuration_name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
            region=ANY_REGION,
            permissions_provider="oidc",
        )
        gc.run()
        # there should only two prompt to ask
        # 1. which account to use (mocked in _prompt_account_id(), not contributing to count)
        # 2. what values customers want to change
        prompt_account_id_mock.assert_called_once()
        click_mock.prompt.assert_called_once()

    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_not_prompt_for_fields_that_are_already_provided_oidc(
        self, prompt_account_id_mock, click_mock, account_id_mock
    ):
        account_id_mock.return_value = "1234567890"
        click_mock.confirm.return_value = False
        click_mock.prompt = Mock(return_value="0")

        github_config = GitHubOidcConfig(
            github_org=ANY_GITHUB_ORG, github_repo=ANY_GITHUB_REPO, deployment_branch=ANY_DEPLOYMENT_BRANCH
        )
        gitlab_config = GitLabOidcConfig(
            gitlab_group=ANY_GITLAB_GROUP, gitlab_project=ANY_GITLAB_PROJECT, deployment_branch=ANY_DEPLOYMENT_BRANCH
        )
        bitbucket_config = BitbucketOidcConfig(ANY_BITBUCKET_REPO_UUID)
        oidc_config = OidcConfig(
            oidc_provider=ANY_OIDC_PROVIDER, oidc_provider_url=ANY_OIDC_PROVIDER_URL, oidc_client_id=ANY_OIDC_CLIENT_ID
        )
        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            stage_configuration_name=ANY_STAGE_CONFIGURATION_NAME,
            permissions_provider="oidc",
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
            region=ANY_REGION,
        )
        gc.run()
        # there should only two prompt to ask
        # 1. which account to use (mocked in _prompt_account_id(), not contributing to count)
        # 2. what values customers want to change
        prompt_account_id_mock.assert_called_once()
        click_mock.prompt.assert_called_once()

    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_not_prompt_for_fields_that_are_already_provided_oidc_gitlab(
        self, prompt_account_id_mock, click_mock, account_id_mock
    ):
        account_id_mock.return_value = "1234567890"
        click_mock.confirm.return_value = False
        click_mock.prompt = Mock(return_value="0")

        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(
            gitlab_group=ANY_GITLAB_GROUP, gitlab_project=ANY_GITLAB_PROJECT, deployment_branch=ANY_DEPLOYMENT_BRANCH
        )
        bitbucket_config = BitbucketOidcConfig(ANY_BITBUCKET_REPO_UUID)
        oidc_config = OidcConfig(
            oidc_provider="gitlab", oidc_provider_url=ANY_OIDC_PROVIDER_URL, oidc_client_id=ANY_OIDC_CLIENT_ID
        )
        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            stage_configuration_name=ANY_STAGE_CONFIGURATION_NAME,
            permissions_provider="oidc",
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
            create_image_repository=True,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,
            region=ANY_REGION,
        )
        gc.run()
        # there should only two prompt to ask
        # 1. which account to use (mocked in _prompt_account_id(), not contributing to count)
        # 2. what values customers want to change
        prompt_account_id_mock.assert_called_once()
        click_mock.prompt.assert_called_once()

    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._validate_oidc_provider_url")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_prompt_for_fields_that_are_not_provided_oidc_bitbucket(
        self, prompt_account_id_mock, click_mock, account_id_mock, oidc_url_validate_mock
    ):
        account_id_mock.return_value = "1234567890"
        click_mock.confirm.return_value = False
        click_mock.prompt = Mock(return_value="0")
        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch=None)
        bitbucket_config = BitbucketOidcConfig(None)
        oidc_config = OidcConfig(oidc_provider="bitbucket-pipelines", oidc_provider_url=None, oidc_client_id=None)

        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,  # Exclude ECR repo, it has its own detailed test below
            permissions_provider="oidc",
        )
        gc.run()
        prompt_account_id_mock.assert_called_once()
        self.assertTrue(self.did_prompt_text_like("Stage configuration Name", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Pipeline execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("CloudFormation execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Artifact bucket", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("region", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("URL of the OIDC provider", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("OIDC Client ID", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Repository UUID", click_mock.prompt))

    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_prompt_for_fields_that_are_not_provided(
        self, prompt_account_id_mock, click_mock, account_id_mock
    ):
        account_id_mock.return_value = "1234567890"
        click_mock.confirm.return_value = False
        click_mock.prompt = Mock(return_value="0")
        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch=None)
        bitbucket_config = BitbucketOidcConfig(None)
        oidc_config = OidcConfig(oidc_provider=ANY_OIDC_PROVIDER, oidc_provider_url=None, oidc_client_id=None)

        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,  # Exclude ECR repo, it has its own detailed test below
        )
        gc.run()
        prompt_account_id_mock.assert_called_once()
        self.assertTrue(self.did_prompt_text_like("Stage configuration Name", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Pipeline IAM user", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Pipeline execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("CloudFormation execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Artifact bucket", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("region", click_mock.prompt))

    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._validate_oidc_provider_url")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_prompt_for_fields_that_are_not_provided_oidc(
        self, prompt_account_id_mock, click_mock, account_id_mock, oidc_url_validate_mock
    ):
        account_id_mock.return_value = "1234567890"
        click_mock.confirm.return_value = False
        click_mock.prompt = Mock(return_value="0")
        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch=None)
        bitbucket_config = BitbucketOidcConfig(None)
        oidc_config = OidcConfig(oidc_provider=ANY_OIDC_PROVIDER, oidc_provider_url=None, oidc_client_id=None)

        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,  # Exclude ECR repo, it has its own detailed test below
            permissions_provider="oidc",
        )
        gc.run()
        prompt_account_id_mock.assert_called_once()
        self.assertTrue(self.did_prompt_text_like("Stage configuration Name", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Pipeline execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("CloudFormation execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Artifact bucket", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("region", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("URL of the OIDC provider", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("OIDC Client ID", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("GitHub Organization", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("GitHub Repository", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("branch that deployments", click_mock.prompt))

    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._validate_oidc_provider_url")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_prompt_for_fields_that_are_not_provided_oidc_gitlab(
        self, prompt_account_id_mock, click_mock, account_id_mock, oidc_url_validate_mock
    ):
        account_id_mock.return_value = "1234567890"
        click_mock.confirm.return_value = False
        click_mock.prompt = Mock(return_value="0")
        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch=None)
        bitbucket_config = BitbucketOidcConfig(None)
        oidc_config = OidcConfig(oidc_provider="gitlab", oidc_provider_url=None, oidc_client_id=None)

        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,  # Exclude ECR repo, it has its own detailed test below
            permissions_provider="oidc",
        )
        gc.run()
        prompt_account_id_mock.assert_called_once()
        self.assertTrue(self.did_prompt_text_like("Stage configuration Name", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Pipeline execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("CloudFormation execution role", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("Artifact bucket", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("region", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("URL of the OIDC provider", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("OIDC Client ID", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("GitLab Group", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("GitLab Project", click_mock.prompt))
        self.assertTrue(self.did_prompt_text_like("branch that deployments", click_mock.prompt))

    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    def test_guided_context_prompts_oidc_url_if_missing_or_invalid(self, click_mock):
        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch=None)
        bitbucket_config = BitbucketOidcConfig(None)
        oidc_config = OidcConfig(oidc_provider=ANY_OIDC_PROVIDER, oidc_provider_url=None, oidc_client_id=None)

        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,  # Exclude ECR repo, it has its own detailed test below
            permissions_provider="oidc",
        )
        click_mock.prompt = Mock(return_value=ANY_OIDC_PROVIDER_URL)

        gc._validate_oidc_provider_url()
        self.assertTrue(self.did_prompt_text_like("Please enter the URL of the OIDC provider", click_mock.echo))

        gc.oidc_config.oidc_provider_url = "Missing_Https://_At_The_Start.com"

        gc._validate_oidc_provider_url()
        self.assertTrue(self.did_prompt_text_like("Please ensure the OIDC URL begins with 'https://", click_mock.echo))

    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    def test_guided_context_oidc_provider_prompt(self, click_mock):
        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch=None)
        bitbucket_config = BitbucketOidcConfig(None)
        oidc_config = OidcConfig(oidc_provider=None, oidc_provider_url=None, oidc_client_id=None)

        gc: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            image_repository_arn=ANY_IMAGE_REPOSITORY_ARN,  # Exclude ECR repo, it has its own detailed test below
            permissions_provider="oidc",
        )
        click_mock.prompt = Mock(return_value="1")

        self.assertTrue(gc.oidc_config.oidc_provider is None)
        gc._prompt_oidc_provider()
        self.assertTrue(self.did_prompt_text_like("Select an OIDC Provider", click_mock.echo))
        self.assertTrue(self.did_prompt_text_like("1 - GitHub Actions", click_mock.echo))
        self.assertTrue(gc.oidc_config.oidc_provider == GITHUB_ACTIONS)

    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.GuidedContext._prompt_account_id")
    def test_guided_context_will_not_prompt_for_not_provided_image_repository_if_no_image_repository_is_required(
        self, prompt_account_id_mock, click_mock, account_id_mock
    ):
        account_id_mock.return_value = "1234567890"
        github_config = GitHubOidcConfig(github_org=None, github_repo=None, deployment_branch=None)
        gitlab_config = GitLabOidcConfig(gitlab_group=None, gitlab_project=None, deployment_branch=None)
        bitbucket_config = BitbucketOidcConfig(None)
        oidc_config = OidcConfig(oidc_provider=ANY_OIDC_PROVIDER, oidc_provider_url=None, oidc_client_id=None)

        # ECR Image Repository choices:
        # 1 - No, My SAM Template won't include lambda functions of Image package-type
        # 2 - Yes, I need a help creating one
        # 3 - I already have an ECR image repository

        gc_without_ecr_info: GuidedContext = GuidedContext(
            github_config=github_config,
            gitlab_config=gitlab_config,
            bitbucket_config=bitbucket_config,
            oidc_config=oidc_config,
            stage_configuration_name=ANY_STAGE_CONFIGURATION_NAME,
            pipeline_user_arn=ANY_PIPELINE_USER_ARN,
            pipeline_execution_role_arn=ANY_PIPELINE_EXECUTION_ROLE_ARN,
            cloudformation_execution_role_arn=ANY_CLOUDFORMATION_EXECUTION_ROLE_ARN,
            artifacts_bucket_arn=ANY_ARTIFACTS_BUCKET_ARN,
        )

        self.assertIsNone(gc_without_ecr_info.image_repository_arn)

        click_mock.confirm.return_value = False  # the user chose to not CREATE an ECR Image repository
        click_mock.prompt.side_effect = [None, "0", "0"]
        gc_without_ecr_info.run()
        self.assertIsNone(gc_without_ecr_info.image_repository_arn)
        self.assertFalse(gc_without_ecr_info.create_image_repository)
        self.assertFalse(self.did_prompt_text_like("Please enter the ECR image repository", click_mock.prompt))

        click_mock.confirm.return_value = True  # the user chose to CREATE an ECR Image repository
        click_mock.prompt.side_effect = [None, None, "0", "0"]
        gc_without_ecr_info.run()
        self.assertIsNone(gc_without_ecr_info.image_repository_arn)
        self.assertTrue(gc_without_ecr_info.create_image_repository)
        self.assertTrue(self.did_prompt_text_like("Please enter the ECR image repository", click_mock.prompt))

        click_mock.confirm.return_value = True  # the user already has a repo
        click_mock.prompt.side_effect = [None, ANY_IMAGE_REPOSITORY_ARN, "0", "0"]
        gc_without_ecr_info.run()
        self.assertFalse(gc_without_ecr_info.create_image_repository)
        self.assertTrue(
            self.did_prompt_text_like("Please enter the ECR image repository", click_mock.prompt)
        )  # we've asked about it
        self.assertEqual(gc_without_ecr_info.image_repository_arn, ANY_IMAGE_REPOSITORY_ARN)

    @staticmethod
    def did_prompt_text_like(txt, click_prompt_mock):
        txt = txt.lower()
        for kall in click_prompt_mock.call_args_list:
            args, kwargs = kall
            if args:
                text = args[0].lower()
            else:
                text = kwargs.get("text", "").lower()
            if txt in text:
                return True
        return False


class TestGuidedContext_prompt_account_id(TestCase):
    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.os.getenv")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.list_available_profiles")
    def test_prompt_account_id_can_display_profiles_and_environment(
        self, list_available_profiles_mock, getenv_mock, click_mock, get_current_account_id_mock
    ):
        getenv_mock.return_value = "not None"
        list_available_profiles_mock.return_value = ["profile1", "profile2"]
        click_mock.prompt.return_value = "1"  # select environment variable
        get_current_account_id_mock.return_value = "account_id"

        guided_context_mock = Mock()
        GuidedContext._prompt_account_id(guided_context_mock)

        click_mock.prompt.assert_called_once_with(
            ANY, show_choices=False, show_default=False, type=click_mock.Choice(["1", "2", "3", "q"])
        )

    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.os.getenv")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.list_available_profiles")
    def test_prompt_account_id_wont_show_environment_option_when_it_doesnt_exist(
        self, list_available_profiles_mock, getenv_mock, click_mock, get_current_account_id_mock
    ):
        getenv_mock.return_value = None
        list_available_profiles_mock.return_value = ["profile1", "profile2"]
        click_mock.prompt.return_value = "1"  # select environment variable
        get_current_account_id_mock.return_value = "account_id"

        guided_context_mock = Mock()
        GuidedContext._prompt_account_id(guided_context_mock)

        click_mock.prompt.assert_called_once_with(
            ANY, show_choices=False, show_default=False, type=click_mock.Choice(["2", "3", "q"])
        )

    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.os.getenv")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.list_available_profiles")
    def test_prompt_account_id_select_environment_unset_self_profile(
        self, list_available_profiles_mock, getenv_mock, click_mock, get_current_account_id_mock
    ):
        getenv_mock.return_value = "not None"
        list_available_profiles_mock.return_value = ["profile1", "profile2"]
        click_mock.prompt.return_value = "1"  # select environment variable
        get_current_account_id_mock.return_value = "account_id"

        guided_context_mock = Mock()
        GuidedContext._prompt_account_id(guided_context_mock)

        self.assertEqual(None, guided_context_mock.profile)

    @parameterized.expand(
        [
            (
                "2",
                "profile1",
            ),
            (
                "3",
                "profile2",
            ),
        ]
    )
    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.os.getenv")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.list_available_profiles")
    def test_prompt_account_id_select_profile_set_profile_to_its_name(
        self,
        profile_selection,
        expected_profile,
        list_available_profiles_mock,
        getenv_mock,
        click_mock,
        get_current_account_id_mock,
    ):
        getenv_mock.return_value = "not None"
        list_available_profiles_mock.return_value = ["profile1", "profile2"]
        click_mock.prompt.return_value = profile_selection
        get_current_account_id_mock.return_value = "account_id"

        guided_context_mock = Mock()
        GuidedContext._prompt_account_id(guided_context_mock)

        self.assertEqual(expected_profile, guided_context_mock.profile)

    @patch("samcli.commands.pipeline.bootstrap.guided_context.sys.exit")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.get_current_account_id")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.click")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.os.getenv")
    @patch("samcli.commands.pipeline.bootstrap.guided_context.list_available_profiles")
    def test_prompt_account_id_select_quit(
        self, list_available_profiles_mock, getenv_mock, click_mock, get_current_account_id_mock, exit_mock
    ):
        getenv_mock.return_value = "not None"
        list_available_profiles_mock.return_value = ["profile1", "profile2"]
        click_mock.prompt.return_value = "q"  # quit
        get_current_account_id_mock.return_value = "account_id"

        guided_context_mock = Mock()
        GuidedContext._prompt_account_id(guided_context_mock)

        exit_mock.assert_called_once_with(0)
