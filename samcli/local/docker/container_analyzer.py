"""
Class for handling the analysis and inspection of Docker containers
"""

import logging
from dataclasses import dataclass

from samcli.local.docker.container import Container
from samcli.local.docker.manager import ContainerManager

LOG = logging.getLogger(__name__)

DEFAULT_OUT_OF_MEMORY = False


@dataclass
class ContainerState:
    out_of_memory: bool


class ContainerAnalyzer:
    def __init__(self, container_manager: ContainerManager, container: Container):
        self.container_manager = container_manager
        self.container = container

    def inspect(self) -> ContainerState:
        """
        Inspect the state of a container by calling the "inspect()" API that Docker provides.
        Extract relevant information into a ContainerState object.

        Returns
        -------
        ContainerState:
            Returns a ContainerState object with relevant container data
        """
        if not self.container.id:
            LOG.debug("Container ID not defined, unable to fetch container state")
            return ContainerState(DEFAULT_OUT_OF_MEMORY)

        state = self.container_manager.inspect(self.container.id)

        if isinstance(state, bool):
            LOG.debug("Unable to fetch container state")
            return ContainerState(DEFAULT_OUT_OF_MEMORY)

        container_state = ContainerState(state.get("State", {}).get("OOMKilled", DEFAULT_OUT_OF_MEMORY))
        LOG.debug("[Container state] OOMKilled %s", container_state.out_of_memory)

        return container_state
