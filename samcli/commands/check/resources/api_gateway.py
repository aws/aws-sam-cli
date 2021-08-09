"""
class object for ApiGateway. Contains the apigateway pbject from the CFN template
"""

from typing import List
from samcli.commands.check.resources.template_resource import TemplateResource


class ApiGateway(TemplateResource):
    def __init__(self, resource_object, resource_type, resource_name, path_to_resource: List[str] = []):
        super().__init__(resource_object, resource_type, resource_name, path_to_resource)
        self.tps = None
        self.parents = []
        self.children = []
