"""
Provide a factory class for IaC project creation
"""
import os

import click

from samcli.lib.iac.cdk.cdk_iac import CdkIacImplementation
from samcli.lib.iac.cdk.exceptions import InvalidIaCPlugin
from samcli.lib.iac.cfn.cfn_iac import CfnIacImplementation
from samcli.lib.iac.plugins_interfaces import ProjectTypes, IaCPluginInterface, SamCliContext

iac_implementations = {
    ProjectTypes.CDK.value: CdkIacImplementation,
    ProjectTypes.CFN.value: CfnIacImplementation,
}


class IaCFactory:
    """
    Generate the appropriate IaC implementation
    get_iac returns an instance of an IaCPluginInterface based on the given context
    detect_project_type returns a string indicating the type of IaC project found
    """

    def __init__(self, context: SamCliContext):
        self._sam_cli_context = context

    def get_iac(self) -> IaCPluginInterface:
        project_type_string = "project_type"
        if project_type_string not in self._sam_cli_context.context_map:
            raise ValueError()
        project_type = self._sam_cli_context.context_map.get(project_type_string)
        if project_type not in iac_implementations:
            raise click.BadOptionUsage(
                option_name="--project-type",
                message=f"{project_type} is an invalid project type option value, the value should be one "
                f"of the following {[ptype.value for ptype in ProjectTypes]} ",
            )
        iac_implementation = iac_implementations.get(project_type)
        if iac_implementation is None:
            raise ValueError()
        return iac_implementation(self._sam_cli_context)

    @staticmethod
    def detect_project_type(path: str) -> str:
        curr_files = os.listdir(path)
        matched_types = []
        for project_type, implementation in iac_implementations.items():
            iac_file_types = implementation.get_iac_file_types()
            # Check if all the files for the IaC type are in the current directory
            if all(file in curr_files for file in iac_file_types):
                matched_types.append(project_type)
        if len(matched_types) != 1:
            raise InvalidIaCPlugin(curr_files)
        return matched_types[0]
