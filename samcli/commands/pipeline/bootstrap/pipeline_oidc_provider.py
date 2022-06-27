"""
Represents a pipeline OIDC provider
"""
from abc import abstractmethod
from typing import List
import click

from samcli.lib.config.samconfig import SamConfig


class PipelineOidcProvider:

    COMMON_OIDC_PARAMETERS_NAMES = ["--oidc-provider-url", "--oidc-client-id"]

    def __init__(self, oidc_parameters: dict) -> None:
        self.oidc_parameters = oidc_parameters

    def verify_common_parameters(self) -> str:
        error_string = ""
        for parameter_name in self.COMMON_OIDC_PARAMETERS_NAMES:
            if not self.oidc_parameters[parameter_name]:
                error_string += f"Missing required parameter '{parameter_name}'\n"
        return error_string

    @abstractmethod
    def verify_subject_claim_parameters(self) -> str:
        pass

    @abstractmethod
    def verify_all_parameters(self) -> None:
        pass

    @abstractmethod
    def save_values(self, samconfig: SamConfig, cmd_names: List[str], section: str) -> None:
        pass


class GitHubOidcProvider(PipelineOidcProvider):

    SUBJECT_CLAIM_PARAMETERS_NAMES = ["--github-org", "--github-repo", "--deployment-branch"]

    def __init__(self, subject_claim_parameters: dict, oidc_parameters: dict) -> None:
        self.subject_claim_parameters = subject_claim_parameters
        super().__init__(oidc_parameters)

    def verify_subject_claim_parameters(self) -> str:
        error_string = ""
        for parameter_name in self.SUBJECT_CLAIM_PARAMETERS_NAMES:
            if not self.subject_claim_parameters[parameter_name]:
                error_string += f"Missing required parameter '{parameter_name}'\n"
        return error_string

    def verify_all_parameters(self) -> None:
        error_string = self.verify_common_parameters()
        error_string += self.verify_subject_claim_parameters()
        if error_string:
            raise click.UsageError("\n" + error_string)

    def save_values(self, samconfig: SamConfig, cmd_names: List[str], section: str) -> None:
        samconfig.put(
            cmd_names=cmd_names, section=section, key="github_org", value=self.subject_claim_parameters["--github-org"]
        )
        samconfig.put(
            cmd_names=cmd_names,
            section=section,
            key="github_repo",
            value=self.subject_claim_parameters["--github-repo"],
        )
        samconfig.put(
            cmd_names=cmd_names,
            section=section,
            key="deployment_branch",
            value=self.subject_claim_parameters["--deployment-branch"],
        )
