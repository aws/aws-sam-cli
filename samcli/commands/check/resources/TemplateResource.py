"""
Super class for all resources
"""
from samcli.lib.providers.provider import Function


class TemplateResource:
    def __init__(self, resource_object: Function, resource_type: str):
        self.resource_object = resource_object
        self.resource_type = resource_type

    def get_resource_object(self) -> Function:
        return self.resource_object

    def get_name(self) -> str:
        return self.resource_object.name

    def get_resource_type(self) -> str:
        return self.resource_type
