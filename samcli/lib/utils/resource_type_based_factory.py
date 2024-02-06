"""Base Factory Abstract Class for Creating Objects Specific to a Resource Type"""

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, Generic, List, Optional, TypeVar

from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_by_id

LOG = logging.getLogger(__name__)

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

    def _get_resource_type(self, resource_identifier: ResourceIdentifier) -> Optional[str]:
        """Get resource type of the resource

        Parameters
        ----------
        resource_identifier : ResourceIdentifier

        Returns
        -------
        Optional[str]
            Resource type of the resource
        """
        resource = get_resource_by_id(self._stacks, resource_identifier)
        if not resource:
            LOG.debug("Resource %s does not exist.", str(resource_identifier))
            return None

        resource_type = resource.get("Type", None)
        if not isinstance(resource_type, str):
            LOG.debug("Resource %s has none string property Type.", str(resource_identifier))
            return None
        return resource_type

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
        resource_type = self._get_resource_type(resource_identifier)
        if not resource_type:
            LOG.debug("Resource %s has invalid property Type.", str(resource_identifier))
            return None
        generator = self._get_generator_mapping().get(resource_type, None)
        return generator
