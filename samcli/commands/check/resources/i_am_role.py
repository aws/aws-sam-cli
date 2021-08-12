"""
Object for an I_AM_Role object in CFN templates
"""
from typing import List
from samcli.lib.providers.provider import Function
from samcli.commands.check.resources.template_resource import TemplateResource


class IAMRole(TemplateResource):
    resource_object: Function
    resource_type: str
    resource_name: str

    def __init__(self, resource_object: Function, resource_type: str, resource_name: str):
        super().__init__(resource_object, resource_type, resource_name)
        self.policies: List = []
