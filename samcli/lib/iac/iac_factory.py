"""
Provide a factory class for IaC project creation
"""
import fnmatch
import os

from samcli.lib.iac.cdk.cdk_iac import CdkIacImplementation
from samcli.lib.iac.cfn.cfn_iac import CfnIacImplementation
from samcli.lib.iac.exceptions import InvalidIaCPluginException, InvalidProjectTypeException
from samcli.lib.iac.plugins_interfaces import IaCPluginInterface, ProjectTypes, SamCliContext

IAC_IMPLEMENTATIONS = {
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
        if project_type_string not in self._sam_cli_context.command_options_map:
            raise ValueError("Project type not found in sam-cli command options")
        project_type = self._sam_cli_context.command_options_map.get(project_type_string)
        if project_type not in IAC_IMPLEMENTATIONS:
            raise InvalidProjectTypeException(
                msg=f"{project_type} is an invalid project type option value, the value should be one "
                f"of the following {[ptype.value for ptype in ProjectTypes]} ",
            )
        iac_implementation = IAC_IMPLEMENTATIONS.get(project_type)
        if iac_implementation is None:
            raise ValueError("IaC implementation type not found in list of valid IaC implementations.")
        return iac_implementation(self._sam_cli_context)

    @staticmethod
    def detect_project_type(path: str) -> str:
        curr_files = os.listdir(path)
        matched_types = []
        for project_type, implementation in IAC_IMPLEMENTATIONS.items():
            iac_file_patterns = implementation.get_iac_file_patterns()
            # Check if all the files for the IaC type are in the current directory
            for pattern in iac_file_patterns:
                if fnmatch.filter(curr_files, pattern):
                    matched_types.append(project_type)
                    break
        if len(matched_types) != 1:
            raise InvalidIaCPluginException(curr_files)
        return matched_types[0]
