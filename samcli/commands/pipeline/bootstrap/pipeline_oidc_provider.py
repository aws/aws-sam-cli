"""
Represents a pipeline OIDC provider
"""
from abc import abstractmethod
from typing import List

import click

from samcli.commands.pipeline.bootstrap.guided_context import BITBUCKET, GITHUB_ACTIONS, GITLAB
from samcli.lib.config.samconfig import SamConfig


class PipelineOidcProvider:
    PROVIDER_URL_PARAMETER = "oidc-provider-url"
    CLIENT_ID_PARAMETER = "oidc-client-id"
    OPENID_CONNECT = "OpenID Connect (OIDC)"

    def __init__(self, oidc_parameters: dict, oidc_parameter_names: List[str], oidc_provider_name: str) -> None:
        self.oidc_parameters = oidc_parameters
        self.oidc_parameter_names = [self.PROVIDER_URL_PARAMETER, self.CLIENT_ID_PARAMETER] + oidc_parameter_names
        self.oidc_provider_name = oidc_provider_name
        self.verify_parameters()

    def verify_parameters(self) -> None:
        """
        Makes sure that all required parameters have been provided
        -------
        """
        error_string = ""
        for parameter_name in self.oidc_parameter_names:
            if not self.oidc_parameters[parameter_name]:
                error_string += f"Missing required parameter '--{parameter_name}'\n"
        if error_string:
            raise click.UsageError("\n" + error_string)

    def save_values(self, samconfig: SamConfig, cmd_names: List[str], section: str) -> None:
        """
        Saves provided values into config file so they can be reused for future calls to bootstrap
        """
        for parameter_name in self.oidc_parameter_names:
            samconfig.put(
                cmd_names=cmd_names,
                section=section,
                key=parameter_name.replace("-", "_"),
                value=self.oidc_parameters[parameter_name],
            )
        samconfig.put(cmd_names=cmd_names, section=section, key="oidc_provider", value=self.oidc_provider_name)
        samconfig.put(cmd_names=cmd_names, section=section, key="permissions_provider", value=self.OPENID_CONNECT)

    @abstractmethod
    def get_subject_claim(self) -> str:
        pass


class GitHubOidcProvider(PipelineOidcProvider):
    """
    Represents a GitHub Actions OIDC provider
    https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
    ----------
    subject_claim_parameters: dict
        Parameters specific to building the subject claim for this provider.
    oidc_parameters: dict
        Parameters common to all providers.
    """

    GITHUB_ORG_PARAMETER_NAME = "github-org"
    GITHUB_REPO_PARAMETER_NAME = "github-repo"
    DEPLOYMENT_BRANCH_PARAMETER_NAME = "deployment-branch"

    def __init__(self, subject_claim_parameters: dict, oidc_parameters: dict) -> None:
        all_oidc_parameters = {**oidc_parameters, **subject_claim_parameters}
        all_oidc_parameter_names = [
            self.GITHUB_ORG_PARAMETER_NAME,
            self.GITHUB_REPO_PARAMETER_NAME,
            self.DEPLOYMENT_BRANCH_PARAMETER_NAME,
        ]
        super().__init__(all_oidc_parameters, all_oidc_parameter_names, GITHUB_ACTIONS)

    def get_subject_claim(self) -> str:
        """
        Returns the subject claim that will be used to establish trust between the OIDC provider and AWS.
        To read more about OIDC claims see the following: https://openid.net/specs/openid-connect-core-1_0.html#Claims
        https://tinyurl.com/github-oidc-token
        In GitHubs case when using the official OIDC action to assume a role the audience claim will always be
        sts.amazon.aws so we must use the subject claim https://tinyurl.com/github-oidc-claim
        -------
        """
        org = self.oidc_parameters["github-org"]
        repo = self.oidc_parameters["github-repo"]
        branch = self.oidc_parameters["deployment-branch"]
        return f"repo:{org}/{repo}:ref:refs/heads/{branch}"


class GitLabOidcProvider(PipelineOidcProvider):
    """
    Represents a GitLab OIDC provider
    https://docs.gitlab.com/ee/integration/openid_connect_provider.html
    ----------
    subject_claim_parameters: dict
        Parameters specific to building the subject claim for this provider.
    oidc_parameters: dict
        Parameters common to all providers.
    """

    GITLAB_PROJECT_PARAMETER_NAME = "gitlab-project"
    GITLAB_GROUP_PARAMETER_NAME = "gitlab-group"
    DEPLOYMENT_BRANCH_PARAMETER_NAME = "deployment-branch"

    def __init__(self, subject_claim_parameters: dict, oidc_parameters: dict) -> None:
        all_oidc_parameters = {**oidc_parameters, **subject_claim_parameters}
        all_oidc_parameter_names = [
            self.GITLAB_PROJECT_PARAMETER_NAME,
            self.GITLAB_GROUP_PARAMETER_NAME,
            self.DEPLOYMENT_BRANCH_PARAMETER_NAME,
        ]
        super().__init__(all_oidc_parameters, all_oidc_parameter_names, GITLAB)

    def get_subject_claim(self) -> str:
        """
        Returns the subject claim that will be used to establish trust between the OIDC provider and AWS.
        To read more about OIDC claims see the following: https://openid.net/specs/openid-connect-core-1_0.html#Claims
        https://docs.gitlab.com/ee/ci/cloud_services/aws/#configure-a-role-and-trust
        To learn more about configuring a role to work with GitLab OIDC through claims see the following
        https://docs.gitlab.com/ee/ci/cloud_services/index.html#configure-a-conditional-role-with-oidc-claims
        -------
        """
        group = self.oidc_parameters["gitlab-group"]
        project = self.oidc_parameters["gitlab-project"]
        branch = self.oidc_parameters["deployment-branch"]
        return f"project_path:{group}/{project}:ref_type:branch:ref:{branch}"


class BitbucketOidcProvider(PipelineOidcProvider):
    """
    Represents a Bitbucket OIDC provider
    https://support.atlassian.com/bitbucket-cloud/docs/integrate-pipelines-with-resource-servers-using-oidc/
    ----------
    subject_claim_parameters: dict
        Parameters specific to building the subject claim for this provider.
    oidc_parameters: dict
        Parameters common to all providers.
    """

    BITBUCKET_REPO_UUID_PARAMETER_NAME = "bitbucket-repo-uuid"

    def __init__(self, subject_claim_parameters: dict, oidc_parameters: dict) -> None:
        all_oidc_parameters = {**oidc_parameters, **subject_claim_parameters}
        all_oidc_parameter_names = [
            self.BITBUCKET_REPO_UUID_PARAMETER_NAME,
        ]
        super().__init__(all_oidc_parameters, all_oidc_parameter_names, BITBUCKET)

    def get_subject_claim(self) -> str:
        """
        Returns the subject claim that will be used to establish trust between the OIDC provider and AWS.
        To read more about OIDC claims see the following: https://openid.net/specs/openid-connect-core-1_0.html#Claims
        To learn more about configuring a role to work with GitLab OIDC through claims see the following
        tinyurl.com/bitbucket-oidc-claims
        -------
        """
        repo_uuid = self.oidc_parameters[self.BITBUCKET_REPO_UUID_PARAMETER_NAME]
        return f"{repo_uuid}:*"
