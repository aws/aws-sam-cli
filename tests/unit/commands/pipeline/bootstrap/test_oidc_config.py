from unittest import TestCase

from samcli.commands.pipeline.bootstrap.oidc_config import (
    OidcConfig,
    GitHubOidcConfig,
    GitLabOidcConfig,
    BitbucketOidcConfig,
)

ANY_OIDC_PROVIDER = "ANY_PROVIDER"
ANY_OIDC_PROVIDER_URL = "ANY_PROVIDER_URL"
ANY_OIDC_CLIENT_ID = "ANY_CLIENT_ID"
ANY_GITHUB_ORG = "ANY_GITHUB_ORG"
ANY_GITHUB_REPO = "ANY_GITHUB_REPO"
ANY_DEPLOYMENT_BRANCH = "ANY_DEPLOYMENT_BRANCH"
ANY_GITLAB_PROJECT = "ANY_GITLAB_PROJECT"
ANY_GITLAB_GROUP = "ANY_GITLAB_GROUP"
ANY_BITBUCKET_REPO_UUID = "ANY_BITBUCKET_REPO_UUID"
ANY_SUBJECT_CLAIM = "ANY_SUBJECT_CLAIM"


class TestOidcConfig(TestCase):
    def setUp(self) -> None:
        self.oidc_config = OidcConfig(
            oidc_provider=ANY_OIDC_PROVIDER, oidc_provider_url=ANY_OIDC_PROVIDER_URL, oidc_client_id=ANY_OIDC_CLIENT_ID
        )
        self.github_config = GitHubOidcConfig(
            github_org=ANY_GITHUB_ORG, github_repo=ANY_GITHUB_REPO, deployment_branch=ANY_DEPLOYMENT_BRANCH
        )
        self.gitlab_config = GitLabOidcConfig(
            gitlab_group=ANY_GITLAB_GROUP, gitlab_project=ANY_GITLAB_PROJECT, deployment_branch=ANY_DEPLOYMENT_BRANCH
        )
        self.bitbucket_config = BitbucketOidcConfig(bitbucket_repo_uuid=ANY_BITBUCKET_REPO_UUID)

    def test_update_oidc_config(self):
        self.oidc_config.update_values(
            oidc_provider="updated_provider", oidc_client_id="updated_client_id", oidc_provider_url="updated_url"
        )

        self.assertEqual(self.oidc_config.oidc_provider, "updated_provider")
        self.assertEqual(self.oidc_config.oidc_client_id, "updated_client_id")
        self.assertEqual(self.oidc_config.oidc_provider_url, "updated_url")

    def test_update_github_config(self):
        self.github_config.update_values(
            github_org="updated_org", github_repo="updated_repo", deployment_branch="updated_branch"
        )

        self.assertEqual(self.github_config.github_org, "updated_org")
        self.assertEqual(self.github_config.github_repo, "updated_repo")
        self.assertEqual(self.github_config.deployment_branch, "updated_branch")

    def test_update_gitlab_config(self):
        self.gitlab_config.update_values(
            gitlab_group="updated_group", gitlab_project="updated_project", deployment_branch="updated_branch"
        )

        self.assertEqual(self.gitlab_config.gitlab_group, "updated_group")
        self.assertEqual(self.gitlab_config.gitlab_project, "updated_project")
        self.assertEqual(self.gitlab_config.deployment_branch, "updated_branch")

    def test_update_bitbucket_config(self):
        self.bitbucket_config.update_values(bitbucket_repo_uuid="updated_uuid")

        self.assertEqual(self.bitbucket_config.bitbucket_repo_uuid, "updated_uuid")
