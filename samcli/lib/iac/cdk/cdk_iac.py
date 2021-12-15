"""
Provide a CDK implementation of IaCPluginInterface
"""
from typing import List

from samcli.lib.iac.plugins_interfaces import IaCPluginInterface, SamCliProject, Stack, LookupPath


# TODO: Implement the new interface methods for the CDK plugin type
class CdkIacImplementation(IaCPluginInterface):
    """
    CDK implementation for the plugins interface.
    read_project parses the CDK and returns a SamCliProject object
    write_project writes the updated project
        back to the build dir and returns true if successful
    update_packaged_locations updates the package locations and r
        returns true if successful
    get_iac_file_types returns a list of file types/patterns associated with
        the CDK project type
    """

    def read_project(self, lookup_paths: List[LookupPath]) -> SamCliProject:
        pass

    def write_project(self, project: SamCliProject, build_dir: str) -> bool:
        pass

    def update_packaged_locations(self, stack: Stack) -> bool:
        pass

    @staticmethod
    def get_iac_file_patterns() -> List[str]:
        return ["cdk.json"]
