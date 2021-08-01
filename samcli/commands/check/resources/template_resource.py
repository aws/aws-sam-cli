"""
Super class for all resources
"""
import abc

from typing import Any, Dict, Union
from samcli.lib.providers.provider import Function


class TemplateResource:
    _resource_object: Union[Dict, Function]
    _resource_type: str

    def __init__(self, resource_object: Union[Dict, Function], resource_type: str):
        """
        Args:
            resource_object (Union[Dict, Function]): The resource object form the template file
            resource_type (str): The resource type
        """
        self._resource_object: Union[Dict, Function] = resource_object
        self._resource_type: str = resource_type

    @property
    def resource_object(self) -> Union[Dict, Function]:
        return self._resource_object

    @property
    @abc.abstractmethod
    def resource_name(self) -> Any:
        raise NotImplementedError()

    @property
    def resource_type(self) -> str:
        return self._resource_type
