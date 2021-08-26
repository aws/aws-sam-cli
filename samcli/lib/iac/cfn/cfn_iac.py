"""
Provide a CFN implementation of IaCPluginInterface
"""
from typing import List

from samcli.lib.iac.plugins_interfaces import IaCPluginInterface, SamCliProject, Stack


class CfnIacImplementation(IaCPluginInterface):
    def read_project(self, lookup_paths: List[str]) -> SamCliProject:
        pass

    def write_project(self, project: SamCliProject, build_dir: str) -> bool:
        pass

    def update_packaged_locations(self, stack: Stack) -> bool:
        pass

    @staticmethod
    def get_iac_file_types() -> List[str]:
        return ["template.yaml"]
