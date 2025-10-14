"""
Container client factory for creating appropriate container clients.

This module provides a factory for creating container clients based on
administrator preferences and availability, implementing the strategy pattern
for container runtime management with instance-based availability detection.
"""

import logging
import os
from typing import Optional

from samcli.cli.context import Context
from samcli.local.docker.container_client import ContainerClient, DockerContainerClient, FinchContainerClient
from samcli.local.docker.container_engine import ContainerEngine
from samcli.local.docker.exceptions import (
    ContainerEnforcementException,
    ContainerNotReachableException,
)
from samcli.local.docker.platform_config import get_platform_handler

LOG = logging.getLogger(__name__)


class ContainerClientFactory:
    """
    Factory that creates client instances and tests their availability.

    This factory creates actual client instances and tests them with ping()
    to determine if they're available and working. It migrates logic from
    the existing get_validated_container_client() function but uses
    instance-based detection.
    """

    @staticmethod
    def create_client() -> "ContainerClient":
        """
        Create the appropriate container client based on availability and preferences.

        Workflow:
        1. Check administrator preference
        2. If preference exists, create preferred client and test availability
        3. If no preference, try Docker first, then Finch

        Returns:
            ContainerClient: The first available and working client

        Raises:
            ContainerEnforcementException: Admin preference not available
            ContainerNotReachableException: No container runtime available
        """
        LOG.debug("ContainerClientFactory.create_client() called")
        admin_preference = ContainerClientFactory.get_admin_container_preference()
        LOG.debug(f"Admin preference: {admin_preference}")

        if admin_preference:
            LOG.debug("Using enforced client creation")
            return ContainerClientFactory._create_enforced_client(admin_preference)

        LOG.debug("Using auto-detected client creation")
        return ContainerClientFactory._create_auto_detected_client()

    @staticmethod
    def _create_enforced_client(preference: str) -> "ContainerClient":
        """
        Create and test client based on administrator enforcement.

        Creates preferred client instance and tests availability with is_available().

        Args:
            preference: The administrator's preferred container runtime

        Returns:
            ContainerClient: The enforced container client strategy

        Raises:
            ContainerEnforcementException: If the preferred runtime is not available
        """
        if preference == ContainerEngine.DOCKER.value:
            # Create Docker client and test availability
            docker_client = ContainerClientFactory._try_create_docker_client()
            if docker_client and docker_client.is_available():
                LOG.debug("Using Docker as Container Engine (enforced).")
                return docker_client
            raise ContainerEnforcementException(
                ContainerClientFactory._get_error_message(
                    "Docker not available but required by administrator preference"
                )
            )

        elif preference == ContainerEngine.FINCH.value:
            # Create Finch client and test availability
            finch_client = ContainerClientFactory._try_create_finch_client()
            if finch_client and finch_client.is_available():
                LOG.debug("Using Finch as Container Engine (enforced).")
                ContainerClientFactory._set_context_runtime_type(finch_client)
                return finch_client
            raise ContainerEnforcementException(
                ContainerClientFactory._get_error_message(
                    "Finch not available but required by administrator preference"
                )
            )

        # Unknown preference - fall back to auto-detection
        return ContainerClientFactory._create_auto_detected_client()

    @staticmethod
    def _create_auto_detected_client() -> ContainerClient:
        """
        Create and test clients based on automatic detection (Docker first, Finch fallback).

        Tries Docker first, then Finch, testing each with is_available().

        Returns:
            ContainerClient: The auto-detected container client strategy

        Raises:
            ContainerNotReachableException: If no container runtime is available
        """
        LOG.debug("Trying Docker client creation")
        # Try Docker first
        docker_client = ContainerClientFactory._try_create_docker_client()
        if docker_client and docker_client.is_available():
            LOG.debug("Using Docker as Container Engine.")
            return docker_client

        LOG.debug("Docker client not available, trying Finch")
        # Try Finch as fallback
        finch_client = ContainerClientFactory._try_create_finch_client()
        if finch_client and finch_client.is_available():
            LOG.debug("Using Finch as Container Engine.")
            ContainerClientFactory._set_context_runtime_type(finch_client)
            return finch_client

        LOG.debug("No container runtime available")
        # No runtime available
        raise ContainerNotReachableException(
            ContainerClientFactory._get_error_message("No container runtime available")
        )

    @staticmethod
    def _try_create_docker_client() -> Optional[DockerContainerClient]:
        """
        Try to create a Docker client.

        Returns:
            DockerContainerClient or None: Client instance if creation succeeds, None if it fails
        """
        try:
            LOG.debug("Attempting to create Docker client")
            # Check if DOCKER_HOST points to Finch (should not be considered Docker)
            docker_host = os.environ.get("DOCKER_HOST", "")
            if docker_host and ContainerClientFactory._is_finch_socket(docker_host):
                return None

            # Create Docker client using default connection
            client = DockerContainerClient()
            LOG.debug("DockerContainerClient instance created successfully")
            return client

        except Exception as e:
            LOG.debug(f"Failed to create Docker client: {e}")
            return None

    @staticmethod
    def _try_create_finch_client() -> Optional[FinchContainerClient]:
        """
        Try to create a Finch client.

        Returns:
            FinchContainerClient or None: Client instance if creation succeeds, None if it fails
        """
        # Store original DOCKER_HOST value to restore later
        original_docker_host = os.environ.get("DOCKER_HOST")

        try:
            LOG.debug("Attempting to create Finch client")

            # Check if Finch is supported on this platform
            socket_path = ContainerClientFactory._get_finch_socket_path()
            LOG.debug(f"Finch socket path: {socket_path}")
            if not socket_path:
                return None

            # Configure environment for Finch
            LOG.debug(f"Setting DOCKER_HOST to: {socket_path}")
            os.environ["DOCKER_HOST"] = socket_path

            # Create Finch client
            LOG.debug("Creating FinchContainerClient instance")
            client = FinchContainerClient()
            LOG.debug("FinchContainerClient instance created successfully")
            return client

        except Exception as e:
            LOG.debug(f"Failed to create Finch client: {e}")
            return None
        finally:
            # Restore original DOCKER_HOST value
            if original_docker_host is not None:
                os.environ["DOCKER_HOST"] = original_docker_host
            elif "DOCKER_HOST" in os.environ:
                del os.environ["DOCKER_HOST"]

    @staticmethod
    def _is_finch_socket(docker_host: str) -> bool:
        """Check if DOCKER_HOST points to a Finch socket."""
        finch_socket_path = ContainerClientFactory._get_finch_socket_path()
        return bool(finch_socket_path and docker_host == finch_socket_path)

    @staticmethod
    def _get_finch_socket_path() -> Optional[str]:
        """Get Finch socket path for this platform."""
        LOG.debug("Getting platform handler for Finch socket path")
        handler = get_platform_handler()
        if not handler or not handler.supports_finch():
            return None
        socket_path = handler.get_finch_socket_path()
        LOG.debug(f"Platform handler returned Finch socket path: {socket_path}")
        return socket_path

    @staticmethod
    def get_admin_container_preference() -> Optional[str]:
        """
        Detect if the device contains administrator managed container preference.
        Read the configuration files for various OS platforms.
        """
        handler = get_platform_handler()
        if not handler:
            return None

        enterprise_preference = handler.read_config()
        return ContainerClientFactory._get_validate_admin_container_preference(enterprise_preference)

    @staticmethod
    def _set_context_runtime_type(client: ContainerClient) -> None:
        """Store the actual container runtime type in context for telemetry."""
        try:
            ctx = Context.get_current_context()
            if ctx:
                runtime_type = client.get_runtime_type()
                setattr(ctx, "actual_container_runtime", runtime_type)
                LOG.debug(f"Stored actual container runtime in context: {runtime_type}")
        except (RuntimeError, ImportError):
            # No Click context available (e.g., in tests) or import error
            pass

    @staticmethod
    def _get_validate_admin_container_preference(container_preference: Optional[str]) -> Optional[str]:
        """
        Validates the administrator container preference.
        Returns None if the preference is not valid.
        """
        if not container_preference:
            return None

        normalized_preference = container_preference.lower().strip()
        LOG.info("Administrator container preference detected.")

        supported_containers = {container.value for container in ContainerEngine}

        def _set_context_preference(value: str) -> None:
            try:
                ctx = Context.get_current_context()
                if ctx:
                    setattr(ctx, "admin_container_preference", value)
            except (RuntimeError, ImportError):
                # No Click context available (e.g., in tests) or import error
                pass

        if normalized_preference in supported_containers:
            LOG.info("Valid administrator container preference: %s.", normalized_preference.capitalize())
            _set_context_preference(normalized_preference)
            return normalized_preference
        else:
            LOG.info("Invalid administrator container preference: %s.", container_preference)
            _set_context_preference("other")
            return None

    @staticmethod
    def _get_error_message(default_message: str) -> str:
        """Get platform-specific error message."""
        handler = get_platform_handler()
        if handler:
            return handler.get_container_not_reachable_message()
        return (
            "Running AWS SAM projects locally requires a container runtime. "
            "Do you have Docker or Finch installed and running?"
        )
