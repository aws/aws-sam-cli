"""
Represents a pipeline OIDC provider
"""
from abc import abstractmethod
from typing import List
import click

from samcli.lib.config.samconfig import SamConfig


class PipelineOidcProvider:

    PROVIDER_URL_PARAMETER = "oidc-provider-url"
    CLIENT_ID_PARAMETER = "oidc-client-id"

    def __init__(self, oidc_parameters: dict, oidc_parameter_names: List[str]) -> None:
        self.oidc_parameters = oidc_parameters
        self.oidc_parameter_names = [self.PROVIDER_URL_PARAMETER, self.CLIENT_ID_PARAMETER] + oidc_parameter_names

    def verify_parameters(self) -> None:
        error_string = ""
        for parameter_name in self.oidc_parameter_names:
            if not self.oidc_parameters[parameter_name]:
                error_string += f"Missing required parameter '--{parameter_name}'\n"
        if error_string:
            raise click.UsageError("\n" + error_string)

    def save_values(self, samconfig: SamConfig, cmd_names: List[str], section: str) -> None:
        for parameter_name in self.oidc_parameter_names:
            samconfig.put(
                cmd_names=cmd_names,
                section=section,
                key=parameter_name.replace("-", "_"),
                value=self.oidc_parameters[parameter_name],
            )

    @abstractmethod
    def get_subject_claim(self) -> str:
        pass


class GitHubOidcProvider(PipelineOidcProvider):

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
        super().__init__(all_oidc_parameters, all_oidc_parameter_names)

    def get_subject_claim(self) -> str:
        org = self.oidc_parameters["github-org"]
        repo = self.oidc_parameters["github-repo"]
        branch = self.oidc_parameters["deployment-branch"]
        return f"repo:{org}/{repo}:ref:refs/heads/{branch}"
