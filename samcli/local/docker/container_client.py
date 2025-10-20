"""
Container client strategy pattern implementation.

This module provides an abstract base class for container clients that enables
a strategy pattern for handling different container runtimes (Docker, Finch, etc.)
while maintaining full API compatibility with docker.DockerClient.

Architecture:
    ContainerClient: Base class that handles environment variable processing and merging
    DockerContainerClient: Standard Docker client using system environment variables
    FinchContainerClient: Finch client that overrides DOCKER_HOST with Finch socket path

Usage:
    # Standard Docker client
    docker_client = DockerContainerClient()

    # Finch client with automatic socket detection
    finch_client = FinchContainerClient()

    # Both provide full DockerClient API compatibility
    docker_client.images.list()
    finch_client.get_runtime_type()  # Returns "finch"
"""

import logging
import os
import tarfile
import tempfile
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple, Union

import docker
from docker.utils import kwargs_from_env

from samcli.local.docker.exceptions import ContainerArchiveImageLoadFailedException
from samcli.local.docker.platform_config import get_finch_socket_path

LOG = logging.getLogger(__name__)


class ContainerClient(docker.DockerClient, ABC):
    """
    Abstract base class for container clients that provides a unified interface
    for different container runtimes while inheriting from docker.DockerClient
    for full compatibility.

    This class implements the strategy pattern to handle runtime-specific behaviors
    while maintaining backward compatibility with existing code that expects
    docker.DockerClient instances.

    The class handles environment variable processing by:
    1. Starting with system environment variables (os.environ)
    2. Applying any environment overrides passed by subclasses
    3. Processing the merged environment with Docker's kwargs_from_env()
    4. Initializing DockerClient with the processed parameters

    Subclasses should call super().__init__(**env_overrides) to provide
    environment variable overrides (e.g., DOCKER_HOST for Finch socket).
    """

    # Initialize socket_path
    socket_path: Optional[str] = None

    def __init__(self, **override_env_params):
        """
        Initialize the container client with environment variable processing and overrides.

        This constructor implements the core environment variable processing logic:
        1. Starts with system environment variables (os.environ)
        2. Applies any environment overrides provided by subclasses
        3. Processes the merged environment using Docker's kwargs_from_env()
        4. Initializes DockerClient with the processed parameters

        This design allows subclasses to override specific environment variables
        (like DOCKER_HOST for Finch) while maintaining full Docker compatibility.

        Args:
            **override_env_params: Environment variable overrides. Common examples:
                - DOCKER_HOST: Override Docker daemon URL (e.g., 'unix:///tmp/finch.sock')
                - DOCKER_TLS_VERIFY: Override TLS verification setting
                - DOCKER_CERT_PATH: Override certificate path

        Example:
            # DockerContainerClient calls: super().__init__()
            # FinchContainerClient calls: super().__init__(DOCKER_HOST='unix:///tmp/finch.sock')
        """

        # Start with system environment variables
        current_env = os.environ.copy()
        current_env.update(override_env_params)
        env_params = kwargs_from_env(environment=current_env)

        # Initialize DockerClient with processed parameters
        LOG.debug(f"Creating container client with parameters: {env_params}")
        super().__init__(**env_params)

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
    def get_socket_path(self) -> Optional[str]:
        """
        Return the socket path being used by this client.

        Returns:
            str: Socket path (e.g., 'unix:///var/run/docker.sock', 'unix://~/.finch/finch.sock')
        """
        pass

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

    The DockerContainerClient uses the standard Docker environment variables:
    - DOCKER_HOST: Docker daemon URL (default: unix:///var/run/docker.sock)
    - DOCKER_TLS_VERIFY: Enable TLS verification
    - DOCKER_CERT_PATH: Path to TLS certificates

    Usage:
        client = DockerContainerClient()
        client.images.list()  # Standard DockerClient API
        client.get_runtime_type()  # Returns "docker"
    """

    def __init__(self):
        """
        Initialize DockerContainerClient using system environment variables.

        Creates a Docker client using the standard Docker environment variables
        without any modifications. This provides the standard Docker behavior
        that users expect.

        The client will use:
        - System DOCKER_HOST environment variable (if set)
        - System DOCKER_TLS_VERIFY environment variable (if set)
        - System DOCKER_CERT_PATH environment variable (if set)
        - Docker's default socket path if no DOCKER_HOST is set

        Example:
            # Uses system environment variables
            client = DockerContainerClient()

            # Full DockerClient API available
            containers = client.containers.list()
            images = client.images.list()
        """
        # Check if DOCKER_HOST points to Finch (should not be considered Docker)
        socket_path = os.environ.get("DOCKER_HOST")
        if socket_path and socket_path == get_finch_socket_path():
            return None

        LOG.debug(f"Creating Docker container client with DOCKER_HOST={socket_path}")
        super().__init__()

    def get_runtime_type(self) -> str:
        """
        Return the runtime type identifier for Docker.

        Returns:
            str: Always returns "docker"
        """
        return "docker"

    def get_socket_path(self) -> Optional[str]:
        """
        Return the socket path being used by this client.

        Returns:
            str: Socket path
        """
        if self.socket_path:
            return self.socket_path

        socket_path = os.environ.get("DOCKER_HOST")
        if socket_path and socket_path == get_finch_socket_path():
            self.socket_path = None
            return self.socket_path

        self.socket_path = socket_path
        return self.socket_path

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


class FinchContainerClient(ContainerClient):
    """
    Finch-specific container client implementation.

    This class provides Finch-specific implementations of container operations
    while maintaining full compatibility with the docker.DockerClient API.
    Handles Finch-specific behaviors like overlayfs issues, manual container filtering,
    and container dependency cleanup.

    The FinchContainerClient automatically detects the Finch socket path and
    overrides the DOCKER_HOST environment variable to connect to Finch instead
    of Docker. All other Docker environment variables (TLS settings, etc.) are
    preserved from the system environment.

    Key differences from DockerContainerClient:
    - Automatically detects and uses Finch socket path
    - Handles Finch-specific overlayfs issues in image loading
    - Uses manual container filtering (no ancestor filter support)
    - Performs container dependency cleanup before image removal

    Usage:
        client = FinchContainerClient()
        client.images.list()  # Same API as DockerClient
        client.get_runtime_type()  # Returns "finch"
    """

    def __init__(self):
        """
        Initialize FinchContainerClient with automatic Finch socket detection.

        Automatically detects the Finch socket path and overrides the DOCKER_HOST
        environment variable to connect to Finch. If no Finch socket is found,
        falls back to using the system environment variables.

        The initialization process:
        1. Detects Finch socket path using ContainerClientFactory
        2. If found, overrides DOCKER_HOST with the Finch socket path
        3. Passes the override to parent ContainerClient for processing
        4. Parent merges with system environment and initializes DockerClient

        Environment variable precedence:
        1. Finch socket path (if detected) overrides DOCKER_HOST
        2. All other system environment variables are preserved
        3. Standard Docker environment processing applies

        Example:
            # Automatically uses Finch socket if available
            client = FinchContainerClient()

            # Full DockerClient API with Finch-specific optimizations
            containers = client.containers.list()
            runtime_type = client.get_runtime_type()  # Returns "finch"
        """

        # Get Finch socket path and create environment override
        socket_path = self.get_socket_path()
        if not socket_path:
            # If socket_path=None mean the platform does not support Finch. Do not create client
            return None
        LOG.debug(f"Creating Finch container client with DOCKER_HOST={socket_path}")
        super().__init__(DOCKER_HOST=socket_path)

    def get_socket_path(self) -> Optional[str]:
        """
        Return the socket path being used by this Finch client.

        Returns:
            str: Socket path
        """
        if self.socket_path:
            return self.socket_path

        self.socket_path = get_finch_socket_path()
        return self.socket_path

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
