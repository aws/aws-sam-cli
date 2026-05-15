"""
Class that provides container service resources (ECS, AgentCore) from a given SAM/CFN template
"""

import logging
from typing import Dict, Iterator, List, NamedTuple, Optional

from samcli.lib.providers.provider import Stack, get_full_path
from samcli.lib.utils.resources import (
    AWS_BEDROCK_AGENTCORE_RUNTIME,
    AWS_ECS_TASK_DEFINITION,
)

LOG = logging.getLogger(__name__)

# Resource types that support container image builds
CONTAINER_IMAGE_RESOURCE_TYPES = [
    AWS_ECS_TASK_DEFINITION,
    AWS_BEDROCK_AGENTCORE_RUNTIME,
]


class ContainerService(NamedTuple):
    """
    Represents a container service resource that needs an image built.
    """

    # Logical ID of the resource
    resource_id: str
    # Full path including stack path
    full_path: str
    # Resource type (e.g., AWS::ECS::TaskDefinition)
    resource_type: str
    # Metadata dict containing Dockerfile, DockerContext, etc.
    metadata: Dict
    # Resource properties
    properties: Dict
    # Stack path
    stack_path: str = ""


class SamContainerServiceProvider:
    """
    Extracts container service resources from SAM/CFN templates that have
    Metadata with Dockerfile and DockerContext, indicating they need image builds.
    """

    def __init__(self, stacks: List[Stack]) -> None:
        self._stacks = stacks
        self._container_services: Dict[str, ContainerService] = {}
        self._extract_container_services()

    def _extract_container_services(self) -> None:
        for stack in self._stacks:
            resources = getattr(stack, "resources", None)
            if not resources or not isinstance(resources, dict):
                continue
            for logical_id, resource in resources.items():
                resource_type = resource.get("Type", "")
                if resource_type not in CONTAINER_IMAGE_RESOURCE_TYPES:
                    continue

                metadata = resource.get("Metadata", {})
                if not self._has_container_build_metadata(metadata):
                    continue

                full_path = get_full_path(stack.stack_path, logical_id)
                properties = resource.get("Properties", {})

                container_service = ContainerService(
                    resource_id=logical_id,
                    full_path=full_path,
                    resource_type=resource_type,
                    metadata=metadata,
                    properties=properties,
                    stack_path=stack.stack_path,
                )
                self._container_services[full_path] = container_service
                LOG.debug("Found container service resource: %s (%s)", full_path, resource_type)

    @staticmethod
    def _has_container_build_metadata(metadata: Optional[Dict]) -> bool:
        """Check if metadata contains the required fields for a container image build."""
        if not metadata:
            return False
        return bool(metadata.get("Dockerfile") and metadata.get("DockerContext"))

    def get(self, name: str) -> Optional[ContainerService]:
        """Get a container service by full path or logical ID."""
        if name in self._container_services:
            return self._container_services[name]
        # Try matching by logical ID alone
        for full_path, service in self._container_services.items():
            if service.resource_id == name:
                return service
        return None

    def get_all(self) -> Iterator[ContainerService]:
        """Return all container services."""
        yield from self._container_services.values()
