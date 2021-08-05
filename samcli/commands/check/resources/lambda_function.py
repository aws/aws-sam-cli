"""
Class object for Lambda Functions. Contains object from template, as well as all data for lambda functions,
excluding pricing info
"""
from typing import List
from samcli.commands.check.resources.template_resource import TemplateResource
from samcli.lib.providers.provider import Function


class LambdaFunction(TemplateResource):
    duration: int
    tps: int
    parents: List
    children: List
    number_of_requests: int
    average_duration: int
    allocated_memory: int
    allocated_memory_unit: str

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
        super().__init__(resource_object, resource_type, resource_name)
        self.duration = -1
        self.tps = -1
        self.parents = []
        self.children = []
        self.number_of_requests = -1
        self.average_duration = -1
        self.allocated_memory = -1
        self.allocated_memory_unit = ""
