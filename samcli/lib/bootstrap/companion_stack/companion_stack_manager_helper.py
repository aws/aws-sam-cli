"""
    Helper class to bridge CLI functions and CompanionStackManager
"""
from typing import Dict, List

from samcli.lib.bootstrap.companion_stack.data_types import ECRRepo

from samcli.commands._utils.template import get_template_function_resource_ids
from samcli.lib.utils.packagetype import IMAGE
from samcli.lib.bootstrap.companion_stack.companion_stack_manager import CompanionStackManager


class CompanionStackManagerHelper:
    missing_repo_functions: List[str]
    auto_ecr_repo_functions: List[str]
    deployed_repos: List[ECRRepo]
    deployed_repo_uris: List[str]
    unreferenced_repos: List[ECRRepo]

    def __init__(
        self,
        stack_name: str,
        region: str,
        s3_bucket: str,
        s3_prefix: str,
        template_file: str,
        specified_image_repos: Dict[str, str],
    ):
        self.function_logical_ids = get_template_function_resource_ids(template_file=template_file, artifact=IMAGE)
        self.missing_repo_functions = list()
        self.auto_ecr_repo_functions = list()
        self.manager = CompanionStackManager(stack_name, region, s3_bucket, s3_prefix)
        self.deployed_repos = self.manager.list_deployed_repos()
        self.deployed_repo_uris = [self.manager.get_repo_uri(repo) for repo in self.deployed_repos]
        self.update_specified_image_repos(specified_image_repos)
        self.unreferenced_repos = self.manager.get_unreferenced_repos()

    def update_specified_image_repos(self, specified_image_repos: Dict[str, str]) -> None:
        """
        Update list of image repos specified for each function.
        updates missing_repo_functions and auto_ecr_repo_functions accordingly.

        Parameters
        ----------
        specified_image_repos: Dict[str, str]
            Dictionary of image repo URIs with key as function logical ID and value as image repo URI
        """
        self.missing_repo_functions.clear()
        self.auto_ecr_repo_functions.clear()
        for function_logical_id in self.function_logical_ids:
            if not specified_image_repos or function_logical_id not in specified_image_repos:
                self.missing_repo_functions.append(function_logical_id)
                continue

            repo_uri = specified_image_repos[function_logical_id]
            if self.manager.is_repo_uri(repo_uri, function_logical_id):
                self.auto_ecr_repo_functions.append(function_logical_id)
        self.manager.set_functions(self.missing_repo_functions + self.auto_ecr_repo_functions)

    def remove_unreferenced_repos_from_mapping(self, image_repositories: Dict[str, str]) -> Dict[str, str]:
        """
        Removes image repos that are not referenced by a function

        Parameters
        ----------
        image_repositories: Dict[str, str]
            Dictionary of image repo URIs with key as function logical ID and value as image repo URI

        Returns
        ----------
        Dict[str, str]
            Copy of image_repositories that have unreferenced image repos removed
        """
        output_image_repositories = image_repositories.copy()
        for function_logical_id, repo_uri in image_repositories.items():
            for repo in self.unreferenced_repos:
                if self.manager.get_repo_uri(repo) == repo_uri:
                    del output_image_repositories[function_logical_id]
                    break
        return output_image_repositories
