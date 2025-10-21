"""
Container client strategy pattern implementation.

This module provides an abstract base class for container clients that enables
a strategy pattern for handling different container runtimes (Docker, Finch, etc.)
while maintaining full API compatibility with docker.DockerClient.
"""

import logging
import os
import tarfile
import tempfile
from abc import ABC, abstractmethod
from typing import Any, List, Tuple, Union

import docker

from samcli.local.docker.exceptions import ContainerArchiveImageLoadFailedException

LOG = logging.getLogger(__name__)


class ContainerClient(docker.DockerClient, ABC):
    """
    Abstract base class for container clients that provides a unified interface
    for different container runtimes while inheriting from docker.DockerClient
    for full compatibility.

    This class implements the strategy pattern to handle runtime-specific behaviors
    while maintaining backward compatibility with existing code that expects
    docker.DockerClient instances.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the container client with docker.DockerClient compatibility."""
        super().__init__(*args, **kwargs)

    @classmethod
    def from_existing_client(cls, existing_client: docker.DockerClient):
        """
        Create strategy client from existing docker client.

        This method allows wrapping an existing docker.DockerClient instance
        with the appropriate strategy implementation.

        Args:
            existing_client: An existing docker.DockerClient instance

        Returns:
            ContainerClient: A new instance of the appropriate strategy class
        """
        # Extract connection details from existing client
        base_url = existing_client.api.base_url if hasattr(existing_client, "api") else None
        version = existing_client.api._version if hasattr(existing_client, "api") else None

        # Create new instance with same connection parameters
        instance = cls(base_url=base_url, version=version)
        return instance

    def is_available(self) -> bool:
        """
        Check if this client instance is available and can connect.

        This method tests actual connectivity by pinging the container runtime.
        It uses the inherited ping() method from docker.DockerClient to test
        if the container runtime is reachable and responding.

        Returns:
            bool: True if the client can successfully connect to the runtime
        """
        try:
            self.ping()
            return True
        except Exception as e:
            LOG.debug(f"Container client availability check failed: {e}")
            return False

    @abstractmethod
    def get_runtime_type(self) -> str:
        """
        Return the runtime type identifier.

        Returns:
            str: Runtime type identifier (e.g., 'docker', 'finch')
        """
        pass

    @abstractmethod
    def load_image_from_archive(self, image_archive) -> Any:
        """
        Load image from archive with runtime-specific handling.

        This method handles the differences between container runtimes when
        loading images from archive files, such as Finch's overlayfs issues.

        Args:
            image_archive: Open file handle to the image archive

        Returns:
            docker.models.images.Image: The loaded image

        Raises:
            ContainerArchiveImageLoadFailedException: If image loading fails
        """
        pass

    @abstractmethod
    def is_dockerfile_error(self, error: Exception) -> bool:
        """
        Check if error is a dockerfile-related error with runtime-specific logic.

        Different container runtimes have different error message patterns for
        dockerfile-related errors. This method provides runtime-specific detection.

        Args:
            error: Exception or error message to check

        Returns:
            bool: True if the error indicates a dockerfile-related issue
        """
        pass

    @abstractmethod
    def list_containers_by_image(self, image_name: str, all_containers: bool = True) -> List[Any]:
        """
        List containers by image with runtime-specific filtering.

        Different container runtimes have different capabilities for filtering
        containers by image. This method provides a unified interface.

        Args:
            image_name: Name or ID of the image to filter by
            all_containers: Whether to include stopped containers

        Returns:
            List[docker.models.containers.Container]: List of matching containers
        """
        pass

    @abstractmethod
    def get_archive(self, container_id: str, path: str) -> Tuple[Any, Any]:
        """
        Get archive from container with runtime-specific handling.

        Different container runtimes handle file extraction differently.
        Docker uses get_archive API, while Finch may need alternative approaches.

        Args:
            container_id: Container ID to extract from
            path: Path inside container to extract

        Returns:
            Tuple[Any, Any]: Archive stream and metadata

        Raises:
            Exception: If archive extraction fails
        """
        pass

    @abstractmethod
    def remove_image_safely(self, image_id: str, force: bool = True) -> None:
        """
        Remove image with runtime-specific cleanup handling.

        Different container runtimes may require different approaches for
        safely removing images, especially when containers depend on them.

        Args:
            image_id: ID or name of the image to remove
            force: Whether to force removal
        """
        pass

    @abstractmethod
    def validate_image_count(self, image_name: str, expected_count_range: Tuple[int, int] = (1, 2)) -> bool:
        """
        Validate pulled images with runtime-specific validation logic.

        Different container runtimes may have different behaviors when pulling
        and managing images. This method provides runtime-aware validation.

        Args:
            image_name: Name of the image to validate
            expected_count_range: Tuple of (min_count, max_count) for validation

        Returns:
            bool: True if the image count is within the expected range
        """
        pass

    def is_finch(self) -> bool:
        """
        Check if this is a Finch client.

        Returns:
            bool: True if this client is connected to Finch
        """
        return self.get_runtime_type() == "finch"

    def is_docker(self) -> bool:
        """
        Check if this is a Docker client.

        Returns:
            bool: True if this client is connected to Docker
        """
        return self.get_runtime_type() == "docker"


class DockerContainerClient(ContainerClient):
    """
    Docker-specific container client implementation.

    This class provides Docker-specific implementations of container operations
    while maintaining full compatibility with the docker.DockerClient API.
    """

    def get_runtime_type(self) -> str:
        """
        Return the runtime type identifier for Docker.

        Returns:
            str: Always returns "docker"
        """
        return "docker"

    def load_image_from_archive(self, image_archive) -> Any:
        """
        Load image from archive using standard Docker image loading logic.

        Uses Docker's standard high-level API for loading images from archive files.
        Validates that the archive contains exactly one image.

        Args:
            image_archive: Open file handle to the image archive

        Returns:
            docker.models.images.Image: The loaded image

        Raises:
            ContainerArchiveImageLoadFailedException: If image loading fails or
                archive contains multiple images
        """
        try:
            result = self.images.load(image_archive)
            [image, *rest] = result
            if len(rest) != 0:
                raise ContainerArchiveImageLoadFailedException(
                    "Failed to load image from archive. Archive must represent a single image"
                )
            return image
        except docker.errors.APIError as e:
            raise ContainerArchiveImageLoadFailedException(f"Failed to load image from archive: {str(e)}") from e

    def is_dockerfile_error(self, error: Union[Exception, str]) -> bool:
        """
        Check if error is a dockerfile-related error for Docker.

        Docker-specific error patterns for dockerfile-related issues typically
        contain "Cannot locate specified Dockerfile" in the error message.

        Args:
            error: Exception or error message to check

        Returns:
            bool: True if the error indicates a dockerfile-related issue
        """
        if isinstance(error, docker.errors.APIError):
            if not error.is_server_error:
                return False
            if not hasattr(error, "explanation") or error.explanation is None:
                return False
            return "Cannot locate specified Dockerfile" in str(error.explanation)
        elif isinstance(error, str):
            return "Cannot locate specified Dockerfile" in error
        return False

    def list_containers_by_image(self, image_name: str, all_containers: bool = True) -> List[Any]:
        """
        List containers by image using Docker's ancestor filter support.

        Docker supports the "ancestor" filter which efficiently finds containers
        that were created from a specific image.

        Args:
            image_name: Name or ID of the image to filter by
            all_containers: Whether to include stopped containers

        Returns:
            List[docker.models.containers.Container]: List of matching containers
        """
        return list(self.containers.list(all=all_containers, filters={"ancestor": image_name}))

    def remove_image_safely(self, image_id: str, force: bool = True) -> None:
        """
        Remove image with standard Docker image removal.

        Uses Docker's standard image removal API with force flag support.
        Handles common exceptions gracefully by logging warnings instead of failing.

        Args:
            image_id: ID or name of the image to remove
            force: Whether to force removal
        """
        try:
            self.images.remove(image_id, force=force)
        except docker.errors.ImageNotFound:
            # Image already removed, continue silently
            LOG.debug(f"Docker image {image_id} not found, may have been already removed")
        except docker.errors.APIError as e:
            # Log but don't fail on cleanup errors
            LOG.warning(f"Failed to remove Docker image {image_id}: {e}")

    def get_archive(self, container_id: str, path: str) -> Tuple[Any, Any]:
        """
        Get archive from container using Docker's standard get_archive API.

        Args:
            container_id: Container ID to extract from
            path: Path inside container to extract

        Returns:
            Tuple[Any, Any]: Archive stream and metadata
        """
        container = self.containers.get(container_id)
        return container.get_archive(path)  # type: ignore[no-any-return]

    def validate_image_count(self, image_name: str, expected_count_range: Tuple[int, int] = (1, 2)) -> bool:
        """
        Validate pulled images with strict Docker validation logic.

        Docker typically has predictable image management behavior, so we can
        use strict validation to ensure the expected number of images exist.

        Args:
            image_name: Name of the image to validate
            expected_count_range: Tuple of (min_count, max_count) for validation

        Returns:
            bool: True if the image count is within the expected range
        """
        try:
            images = self.images.list(name=image_name)
            image_count = len(images)
            return expected_count_range[0] <= image_count <= expected_count_range[1]
        except docker.errors.APIError as e:
            LOG.warning(f"Failed to validate image count for {image_name}: {e}")
            return False

    @classmethod
    def from_existing_client(cls, existing_client: docker.DockerClient):
        """
        Create DockerContainerClient from existing docker client.

        This method allows wrapping an existing docker.DockerClient instance
        with the DockerContainerClient strategy implementation.

        Args:
            existing_client: An existing docker.DockerClient instance

        Returns:
            DockerContainerClient: A new instance wrapping the existing client
        """
        # Extract connection details from existing client
        base_url = existing_client.api.base_url if hasattr(existing_client, "api") else None
        version = existing_client.api._version if hasattr(existing_client, "api") else None

        # Create new instance with same connection parameters
        instance = cls(base_url=base_url, version=version)
        return instance


class FinchContainerClient(ContainerClient):
    """
    Finch-specific container client implementation.

    This class provides Finch-specific implementations of container operations
    while maintaining full compatibility with the docker.DockerClient API.
    Handles Finch-specific behaviors like overlayfs issues, manual container filtering,
    and container dependency cleanup.
    """

    def __init__(self, *args, **kwargs):
        """Initialize Finch container client with automatic socket configuration."""
        # Import here to avoid circular imports
        from samcli.local.docker.container_client_factory import ContainerClientFactory

        # Get Finch socket path if not explicitly provided
        if "base_url" not in kwargs:
            socket_path = ContainerClientFactory._get_finch_socket_path()
            if socket_path:
                kwargs["base_url"] = socket_path

        super().__init__(*args, **kwargs)

    def get_runtime_type(self) -> str:
        """
        Return the runtime type identifier for Finch.

        Returns:
            str: Always returns "finch"
        """
        return "finch"

    def load_image_from_archive(self, image_archive) -> Any:
        """
        Load image from archive with Finch overlayfs workaround using raw API fallback.

        Finch has known issues with overlayfs when loading images from archives.
        This method first tries the standard approach, then falls back to using
        the raw API to work around overlayfs issues.

        Args:
            image_archive: Open file handle to the image archive

        Returns:
            docker.models.images.Image: The loaded image

        Raises:
            ContainerArchiveImageLoadFailedException: If image loading fails
        """
        try:
            # Try standard approach first
            result = self.images.load(image_archive)
            [image, *rest] = result
            if len(rest) != 0:
                raise ContainerArchiveImageLoadFailedException(
                    "Failed to load image from archive. Archive must represent a single image"
                )
            return image
        except (docker.errors.ImageNotFound, docker.errors.APIError) as e:
            # Handle Finch overlayfs issue with raw API fallback
            LOG.debug(f"Standard image loading failed, trying raw API fallback: {e}")
            return self._load_with_raw_api(image_archive, e)

    def _load_with_raw_api(self, image_archive, original_error) -> Any:
        """
        Handle Finch overlayfs workaround using raw API.

        This method uses the raw Docker API to work around Finch's overlayfs issues
        when loading images from archives. It parses the response stream to find
        the loaded image reference.

        Args:
            image_archive: Open file handle to the image archive
            original_error: The original error that triggered this fallback

        Returns:
            docker.models.images.Image: The loaded image

        Raises:
            ContainerArchiveImageLoadFailedException: If raw API loading also fails
        """
        try:
            # Reset file pointer to beginning
            image_archive.seek(0)

            # Use raw API to load image
            result = self.api.load_image(image_archive)

            loaded_digest = None
            for line in result:
                if isinstance(line, dict) and "stream" in line:
                    stream_text = line["stream"]
                    if "Loaded image:" in stream_text:
                        loaded_ref = stream_text.split("Loaded image: ", 1)[1].strip()
                        # Skip overlayfs artifacts
                        if loaded_ref and loaded_ref != "overlayfs:":
                            loaded_digest = loaded_ref
                            break

            if loaded_digest and loaded_digest != "overlayfs:":
                return self.images.get(loaded_digest)

            # If we couldn't find a valid loaded image reference, raise error
            raise ContainerArchiveImageLoadFailedException(
                "Failed to load image from archive using raw API fallback", original_error
            )

        except Exception as e:
            raise ContainerArchiveImageLoadFailedException(
                f"Failed to load image from archive with Finch overlayfs workaround: {str(e)}", original_error
            ) from e

    def is_dockerfile_error(self, error: Union[Exception, str]) -> bool:
        """
        Check if error is a dockerfile-related error for Finch-specific error patterns.

        Finch-specific error patterns for dockerfile-related issues typically
        contain "no such file or directory" in the error message when a Dockerfile
        cannot be found.

        Args:
            error: Exception or error message to check

        Returns:
            bool: True if the error indicates a dockerfile-related issue
        """
        if isinstance(error, docker.errors.APIError):
            if not error.is_server_error:
                return False
            if not hasattr(error, "explanation") or error.explanation is None:
                return False
            error_text = str(error.explanation)
        elif isinstance(error, str):
            error_text = error
        else:
            return False

        return "no such file or directory" in error_text.lower()

    def list_containers_by_image(self, image_name: str, all_containers: bool = True) -> List[Any]:
        """
        List containers by image with manual filtering (no ancestor filter support).

        Finch (nerdctl) does not support the "ancestor" filter that Docker provides,
        so we need to manually filter containers by inspecting their image references.

        Args:
            image_name: Name or ID of the image to filter by
            all_containers: Whether to include stopped containers

        Returns:
            List[docker.models.containers.Container]: List of matching containers
        """
        try:
            all_containers_list = self.containers.list(all=all_containers)
            matching_containers = []

            for container in all_containers_list:
                try:
                    # Check if container image matches our expected image
                    if hasattr(container, "image") and container.image:
                        image_tags = getattr(container.image, "tags", [])
                        # Check if any of the image tags contain our image name
                        if any(image_name in tag for tag in image_tags):
                            matching_containers.append(container)
                        # Also check the image ID directly
                        elif hasattr(container.image, "id") and image_name in container.image.id:
                            matching_containers.append(container)
                except Exception as e:
                    # Skip containers we can't inspect (they might be from other tools)
                    LOG.debug(f"Skipping container inspection due to error: {e}")
                    continue

            return matching_containers

        except docker.errors.APIError as e:
            LOG.warning(f"Failed to list containers by image {image_name}: {e}")
            return []

    def remove_image_safely(self, image_id: str, force: bool = True) -> None:
        """
        Remove image with container dependency cleanup before image removal.

        Finch may have stricter dependency checking than Docker, so we need to
        stop and remove any containers using the image before attempting to
        remove the image itself.

        Args:
            image_id: ID or name of the image to remove
            force: Whether to force removal
        """
        try:
            # First, stop and remove any containers using this image to break dependencies
            containers = self.list_containers_by_image(image_id, all_containers=True)
            for container in containers:
                try:
                    # Stop the container if it's running
                    if container.status == "running":
                        container.stop()
                    # Remove the container
                    container.remove(force=True)
                    LOG.debug(f"Removed container {container.id} that was using image {image_id}")
                except (docker.errors.NotFound, docker.errors.APIError) as e:
                    # Container might already be stopped/removed
                    LOG.debug(f"Container cleanup warning for {container.id}: {e}")
                    continue

            # Now remove the image
            self.images.remove(image_id, force=force)
            LOG.debug(f"Successfully removed Finch image {image_id}")

        except docker.errors.ImageNotFound:
            # Image already removed, continue silently
            LOG.debug(f"Finch image {image_id} not found, may have been already removed")
        except docker.errors.APIError as e:
            # Log but don't fail on cleanup errors
            LOG.warning(f"Failed to remove Finch image {image_id}: {e}")

    def get_archive(self, container_id: str, path: str) -> Tuple[Any, Any]:
        """
        Get archive from container with Finch mount handling.
        Finch may have issues with get_archive, so we try the standard approach first,
        then fall back to extracting from mount information if needed.
        """
        container = self.containers.get(container_id)

        try:
            # Try standard Docker API first
            return container.get_archive(path)  # type: ignore[no-any-return]
        except Exception as e:
            # Check if this is a Finch-specific error that we can work around
            error_str = str(e)
            if any(indicator in error_str for indicator in ["mount-snapshot", "no such file or directory"]):
                LOG.debug(f"Standard get_archive failed for Finch, trying mount fallback: {e}")
                return self._get_archive_from_mount(container, path)
            # If it's not a known Finch issue, re-raise the original exceptio
            raise

    def _get_archive_from_mount(self, container, path: str) -> Tuple[Any, Any]:
        """
        Get archive from Finch container using mount information.

        Args:
            container: Container instance to extract from
            path: Path inside container to extract

        Returns:
            Tuple[Any, Any]: Archive stream and metadata
        """

        # Get container mount information
        mounts = container.attrs.get("Mounts", [])

        # Find the mount that contains our artifacts
        for mount in mounts:
            if mount.get("Type") == "bind" and "/tmp/samcli" in mount.get("Destination", ""):
                source_path = mount.get("Source", "")
                dest_path = mount.get("Destination", "")

                # Calculate the host path for the artifacts
                relative_path = path.replace(dest_path, "").lstrip("/")
                host_artifacts_path = os.path.join(source_path, relative_path)

                if os.path.exists(host_artifacts_path):
                    # Create tar archive from host path and return as iterable stream
                    with tempfile.NamedTemporaryFile() as temp_tar:
                        with tarfile.open(temp_tar.name, "w") as tar:
                            tar.add(host_artifacts_path, arcname=".")

                        temp_tar.seek(0)
                        tar_data = temp_tar.read()
                        # Return iterable that yields chunks like Docker's get_archive
                        return (iter([tar_data]), {})

        raise RuntimeError(f"Could not find artifacts in Finch mounts for path: {path}")

    def validate_image_count(self, image_name: str, expected_count_range: Tuple[int, int] = (1, 2)) -> bool:
        """
        Validate pulled images with flexible Finch validation logic.

        Finch may have different image management behavior compared to Docker,
        so we use more flexible validation that focuses on ensuring at least
        the minimum expected number of images exist.

        Args:
            image_name: Name of the image to validate
            expected_count_range: Tuple of (min_count, max_count) for validation

        Returns:
            bool: True if the image count meets the minimum requirement
        """
        try:
            images = self.images.list(name=image_name)
            image_count = len(images)
            # Finch may have different image management behavior, so be more flexible
            # Focus on ensuring we have at least the minimum expected images
            return image_count >= expected_count_range[0]
        except docker.errors.APIError as e:
            LOG.warning(f"Failed to validate image count for {image_name}: {e}")
            return False

    @classmethod
    def from_existing_client(cls, existing_client: docker.DockerClient):
        """
        Create FinchContainerClient from existing docker client for wrapping existing Finch clients.

        This method allows wrapping an existing docker.DockerClient instance
        (which may be connected to Finch) with the FinchContainerClient strategy implementation.

        Args:
            existing_client: An existing docker.DockerClient instance connected to Finch

        Returns:
            FinchContainerClient: A new instance wrapping the existing client
        """
        # Extract connection details from existing client
        base_url = existing_client.api.base_url if hasattr(existing_client, "api") else None
        version = existing_client.api._version if hasattr(existing_client, "api") else None

        # Create new instance with same connection parameters
        instance = cls(base_url=base_url, version=version)
        return instance
