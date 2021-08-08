"""
Object for an I_AM_Role object in CFN templates
"""
from samcli.commands.check.resources.template_resource import TemplateResource


class IAMRole(TemplateResource):
    def __init__(self, resource_object, resource_type, resource_name):
        super().__init__(resource_object, resource_type, resource_name)
        self.policies = []
