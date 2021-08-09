"""
Super class for all resources
"""

from typing import List
from samcli.lib.providers.provider import Function


class TemplateResource:
    resource_object: Function
    resource_type: str
    resource_name: str
    path_to_resource: List[str]

    def __init__(
        self, resource_object: Function, resource_type: str, resource_name: str, path_to_resource: List[str] = []
    ):
        """
        Parameters
        ----------
            resource_object: Function
                The resource object form the template file
            resource_type: str
                The resource type
            resource_name: str
                The name of the resource
            path_to_resource: List[str]
                A list of the path taken to the current state of a resource
        """
        self.resource_object = resource_object
        self.resource_type = resource_type
        self.resource_name = resource_name
        self.path_to_resource = path_to_resource
