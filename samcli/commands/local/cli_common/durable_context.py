"""
Context manager for durable functions emulator operations.
"""

import logging
from typing import Optional

from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.local.docker.durable_functions_emulator_container import DurableFunctionsEmulatorContainer

LOG = logging.getLogger(__name__)


class DurableContext:
    """
    Context manager for durable functions emulator operations.
    Provides a clean interface for CLI commands to interact with the emulator.
    Automatically reuses existing running containers when possible.
    """

    def __init__(self):
        """
        Initialize the durable context.
        """
        self._emulator: Optional[DurableFunctionsEmulatorContainer] = None
        self._reused_container = False

    def __enter__(self) -> "DurableContext":
        """
        Start the emulator container or attach to an already running one
        """
        self._emulator = DurableFunctionsEmulatorContainer()
        self._reused_container = self._emulator.start_or_attach()
        return self

    def __exit__(self, *args):
        """
        Clean up emulator container only if we created it.
        """
        if self._emulator and not self._reused_container:
            LOG.debug("Stopping durable functions emulator container")
            self._emulator.stop()
        elif self._reused_container:
            LOG.debug("Leaving existing durable functions emulator container running")

    @property
    def client(self) -> DurableFunctionsClient:
        """
        Get the durable functions client.

        Returns:
            DurableFunctionsClient instance

        Raises:
            RuntimeError: If context is not initialized
        """
        if not self._emulator or not self._emulator.lambda_client:
            raise RuntimeError("DurableContext not initialized - use within 'with' statement")

        client: DurableFunctionsClient = self._emulator.lambda_client
        return client
