"""
Represents a pipeline OIDC provider
"""
from typing import Optional


class OidcConfig:
    def __init__(
        self, oidc_provider: Optional[str], oidc_provider_url: Optional[str], oidc_client_id: Optional[str]
    ) -> None:
        self.oidc_provider = oidc_provider
        self.oidc_provider_url = oidc_provider_url
        self.oidc_client_id = oidc_client_id

    def get_oidc_parameters(self) -> dict:
        return {
            "oidc-provider-url": self.oidc_provider_url,
            "oidc-provider": self.oidc_provider,
            "oidc-client-id": self.oidc_client_id,
        }

    def update_values(
        self, oidc_provider: Optional[str], oidc_provider_url: Optional[str], oidc_client_id: Optional[str]
    ) -> None:
        self.oidc_provider = oidc_provider if oidc_provider else self.oidc_provider
        self.oidc_provider_url = oidc_provider_url if oidc_provider_url else self.oidc_provider_url
        self.oidc_client_id = oidc_client_id if oidc_client_id else self.oidc_client_id


class GitHubOidcConfig:
    def __init__(self, github_org: Optional[str], github_repo: Optional[str], deployment_branch: Optional[str]) -> None:
        self.github_org = github_org
        self.github_repo = github_repo
        self.deployment_branch = deployment_branch

    def get_oidc_parameters(self) -> dict:
        return {
            "github-org": self.github_org,
            "github-repo": self.github_repo,
            "deployment-branch": self.deployment_branch,
        }

    def update_values(
        self, github_org: Optional[str], github_repo: Optional[str], deployment_branch: Optional[str]
    ) -> None:
        self.github_org = github_org if github_org else self.github_org
        self.github_repo = github_repo if github_repo else self.github_repo
        self.deployment_branch = deployment_branch if deployment_branch else self.deployment_branch


class GitLabOidcConfig:
    def __init__(
        self, gitlab_group: Optional[str], gitlab_project: Optional[str], deployment_branch: Optional[str]
    ) -> None:
        self.gitlab_group = gitlab_group
        self.gitlab_project = gitlab_project
        self.deployment_branch = deployment_branch

    def get_oidc_parameters(self) -> dict:
        return {
            "gitlab-group": self.gitlab_group,
            "gitlab-project": self.gitlab_project,
            "deployment-branch": self.deployment_branch,
        }

    def update_values(
        self, gitlab_group: Optional[str], gitlab_project: Optional[str], deployment_branch: Optional[str]
    ) -> None:
        self.gitlab_group = gitlab_group if gitlab_group else self.gitlab_group
        self.gitlab_project = gitlab_project if gitlab_project else self.gitlab_project
        self.deployment_branch = deployment_branch if deployment_branch else self.deployment_branch


class BitbucketOidcConfig:
    def __init__(self, bitbucket_repo_uuid: Optional[str]) -> None:
        self.bitbucket_repo_uuid = bitbucket_repo_uuid

    def get_oidc_parameters(self) -> dict:
        return {
            "bitbucket-repo-uuid": self.bitbucket_repo_uuid,
        }

    def update_values(self, bitbucket_repo_uuid: Optional[str]) -> None:
        self.bitbucket_repo_uuid = bitbucket_repo_uuid if bitbucket_repo_uuid else self.bitbucket_repo_uuid
