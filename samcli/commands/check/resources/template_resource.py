"""
Super class for all resources
"""

from samcli.lib.providers.provider import Function


class TemplateResource:
    resource_object: Function
    resource_type: str
    resource_name: str

    def __init__(self, resource_object: Function, resource_type: str, resource_name: str):
        """
        Parameters
        ----------
            resource_object: Function
                The resource object form the template file
            resource_type: str
                The resource type
            resource_name: str
                The name of the resource
        """
        self.resource_object: Function = resource_object
        self.resource_type: str = resource_type
        self.resource_name: str = resource_name
