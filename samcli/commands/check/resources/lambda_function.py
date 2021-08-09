"""
Class object for Lambda Functions. Contains object from template, as well as all data for lambda functions,
excluding pricing info
"""
from typing import List, Optional, Union
from samcli.commands.check.resources.template_resource import TemplateResource
from samcli.commands.check.resources.api_gateway import ApiGateway
from samcli.commands.check.resources.dynamo_db import DynamoDB
from samcli.commands.check.resources.lambda_function_permission import LambdaFunctionPermission
from samcli.lib.providers.provider import Function


class LambdaFunction(TemplateResource):
    duration: int
    tps: int
    parents: List
    children: List
    permission: Optional[LambdaFunctionPermission]
    entry_point_resource: Union[ApiGateway, DynamoDB, None]

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
        """
        super().__init__(resource_object, resource_type, resource_name, path_to_resource)
        self.duration = -1
        self.tps = -1
        self.parents = []
        self.children = []
        self.permission = None
        self.entry_point_resource = None

    def copy_data(self):
        """
        Copies data from cirrent resource over to a new one. This is what
        happens when a snapshot of the graph occurs for analyzing reources

        Returns:
            new_lambda_function: LambdaFunction
                Returns the new, copied, independent lambda function object
        """
        old_resource_object = self.resource_object
        old_resource_type = self.resource_type
        old_resource_name = self.resource_name
        old_duration = self.duration
        old_tps = self.tps
        old_parents = self.parents
        old_children = self.children
        old_permission = self.permission
        old_entry_point_resource = self.entry_point_resource
        old_path_to_resource = self.path_to_resource

        new_lambda_function = LambdaFunction(
            old_resource_object, old_resource_type, old_resource_name, old_path_to_resource
        )

        new_lambda_function.duration = int(old_duration)
        new_lambda_function.tps = old_tps
        new_lambda_function.parents = old_parents
        new_lambda_function.children = old_children
        new_lambda_function.permission = old_permission
        new_lambda_function.entry_point_resource = old_entry_point_resource

        return new_lambda_function
