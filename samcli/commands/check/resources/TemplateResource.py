"""
Super class for all resources
"""
from samcli.lib.providers.provider import Function


class TemplateResource:
    def __init__(self, resource_object: Function, resource_type: str):
        self._resource_object = resource_object
        self._resource_type = resource_type

    def get_resource_object(self) -> Function:
        return self._resource_object

    def get_name(self) -> str:
        return self._resource_object.name

    def get_resource_type(self) -> str:
        return self._resource_type

    # Property objects
    resource_object = property(get_resource_object)
    resource_type = property(get_resource_type)
    resource_name = property(get_name)
