"""
Super class for all resources
"""
from samcli.lib.providers.provider import Function


class TemplateResource:
    def __init__(self, resource_object: Function, resource_type: str):
        self._resource_object = resource_object
        self._resource_type = resource_type

    @property
    def resource_object(self) -> Function:
        return self._resource_object

    @property
    def resource_name(self) -> str:
        return self._resource_object.name

    @property
    def resource_type(self) -> str:
        return self._resource_type
