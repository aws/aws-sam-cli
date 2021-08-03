"""
Class object for Lambda Functions. Contains object from template, as well as all data for lambda functions,
excluding pricing info
"""
from typing import List, Any
from samcli.lib.providers.provider import Function
from samcli.commands.check.resources.template_resource import TemplateResource


class LambdaFunction(TemplateResource):
    duration: int
    tps: int
    parents: List
    children: List

    def __init__(self, resource_object: Function, resource_type: str):
        """
        Args:
            resource_object (Function): The resource object form the template file
            resource_type (str): The resource type
        """
        super().__init__(resource_object, resource_type)
        self.duration = -1
        self.tps = -1
        self.parents: List = []
        self.children: List = []

    @property
    def resource_name(self) -> Any:
        return self._resource_object.name
