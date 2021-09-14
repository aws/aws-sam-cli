"""
Provide IacProjectResolver to process IaC project information from command line options
"""

import logging
import os

from typing import List, Tuple, Optional
from click import Context
import click

from samcli.lib.iac.interface import ProjectTypes, IacPlugin, Project
from samcli.lib.iac.utils.helpers import get_iac_plugin

LOG = logging.getLogger(__name__)


class IacProjectResolver:
    """
    Use this class to resolve project content from the command line options. It does the following thing before
    do_cli()
    - Detect project type, and compare with the one from --project-type
    - Validate the command line options related to plugin interface,
    - Get the IaCPlugin, and the project information, for future processing
    """

    def __init__(self, click_ctx: Context):
        self._ctx = click_ctx
        self._params = click_ctx.params

    def resolve_project(
        self, include_build_folder: bool = True, with_build: bool = False
    ) -> Tuple[str, IacPlugin, Project]:
        """
        Validate the command line options related to different plugin/project_type
        If SAM template file exists, project_type will be “CFN”
        Else if cdk.json exists in the root directory, project_type will be “CDK”
        Else, project_type will be “CFN”

        :param include_build_folder: A boolean to set whether to search build folder (.aws-sam) or not.
        :param with_build: A boolean to set whether to load project from build folder (.aws-sam) or not.
        :param require_stack: a boolean flag to set whether --stack-name is required or not
        :return: tuple (Project type, IaCPlugin, Project)
        """
        project_type = self._resolve_project_type(include_build_folder)
        iac_plugin, project = get_iac_plugin(project_type, self._params, with_build)
        return project_type, iac_plugin, project

    def _resolve_project_type(self, include_build_folder: bool) -> str:
        """
        Determine the type of IaC Project to use.
        If SAM template file exists, project_type will be “CFN”
        Else if cdk.json exists in the root directory, project_type will be “CDK”
        Else, project_type will be “CFN”

        :param include_build_folder: A boolean to set whether to search build folder (.aws-sam) or not.
        :return: Project type
        """
        project_type_from_cmd_line = self._params.get("project_type")
        return self._get_project_type(project_type_from_cmd_line, include_build_folder)

    def _get_project_type(self, project_type_from_cmd_line: Optional[str], include_build_folder: bool) -> str:

        detected_project_type = self._detect_project_type(include_build_folder)

        if not project_type_from_cmd_line:
            return detected_project_type

        if project_type_from_cmd_line != detected_project_type:
            raise click.BadOptionUsage(
                option_name="--project-type",
                ctx=self._ctx,
                message=f"It seems your project type is {detected_project_type}. "
                f"However, you specified {project_type_from_cmd_line} in --project-type",
            )
        LOG.debug("Using customized project type %s.", project_type_from_cmd_line)
        return project_type_from_cmd_line

    def _detect_project_type(self, include_build_folder: bool) -> str:

        LOG.debug("Determining project type...")

        if self._find_cfn_template(include_build_folder):
            LOG.debug("The project is a CFN project.")
            return ProjectTypes.CFN.value
        if self._find_cdk_file():
            LOG.debug("The project is a CDK project.")
            return ProjectTypes.CDK.value
        return ProjectTypes.CFN.value

    def _find_cfn_template(self, include_build_folder: bool) -> bool:
        """
        Determine if template file exists
        """
        search_paths = ["template.yaml", "template.yml"]

        if include_build_folder:
            search_paths.insert(0, os.path.join(".aws-sam", "build", "template.yaml"))

        return self._find_in_paths(search_paths)

    def _find_cdk_file(self) -> bool:
        """
        Determine if cdk.json exists in the root directory
        """
        search_paths = ["cdk.json"]
        return self._find_in_paths(search_paths)

    @staticmethod
    def _find_in_paths(search_paths: List[str]) -> bool:
        for path in search_paths:
            if os.path.exists(path):
                return True
        return False
