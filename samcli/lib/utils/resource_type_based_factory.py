"""Base Factory Abstract Class for Creating Objects Specific to a Resource Type"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, Generic, List, Optional, TypeVar

from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_by_id

T = TypeVar("T")  # pylint: disable=invalid-name


class ResourceTypeBasedFactory(ABC, Generic[T]):
    def __init__(self, stacks: List[Stack]) -> None:
        self._stacks = stacks

    @abstractmethod
    def _get_generator_mapping(self) -> Dict[str, Callable]:
        """
        Returns
        -------
        Dict[str, GeneratorFunction]
            Mapping between resource type and generator function
        """
        raise NotImplementedError()

    def _get_generator_function(self, resource_identifier: ResourceIdentifier) -> Optional[Callable]:
        """Create an appropriate T object based on stack resource type

        Parameters
        ----------
        resource_identifier : ResourceIdentifier
            Resource identifier of the resource

        Returns
        -------
        Optional[T]
            Object T for the resource. Returns None if resource cannot be
            found or have no associating T generator function.
        """
        resource = get_resource_by_id(self._stacks, resource_identifier)
        if not resource:
            return None

        resource_type = resource.get("Type")
        if not resource_type:
            return None

        generator = self._get_generator_mapping().get(resource_type, None)

        if not generator:
            return None

        return generator
