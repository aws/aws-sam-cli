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
        self.permission = None
        self.entry_point_resource = None

    def add_child(self, child):
        # REMOVE
        self.children.append(child)

    def copy_data(self):
        old_resource_object = self.resource_object
        old_resource_type = self.resource_type
        old_resource_name = self.resource_name
        old_duration = self.duration
        old_tps = self.tps
        old_parents = self.parents
        old_children = self.children
        old_permission = self.permission
        old_entry_point_resource = self.entry_point_resource

        new_lambda_function = LambdaFunction(old_resource_object, old_resource_type, old_resource_name)

        new_lambda_function.duration = int(old_duration)
        new_lambda_function.tps = old_tps
        new_lambda_function.parents = old_parents
        new_lambda_function.children = old_children
        new_lambda_function.permission = old_permission
        new_lambda_function.entry_point_resource = old_entry_point_resource

        return new_lambda_function
