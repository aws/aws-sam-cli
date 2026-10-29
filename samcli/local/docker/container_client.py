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

import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union, cast

import docker
from docker.utils import kwargs_from_env

from samcli.cli.global_config import GlobalConfig
from samcli.lib.constants import DOCKER_MIN_API_VERSION, DOCKER_MIN_API_VERSION_FALLBACK
from samcli.local.docker.exceptions import (
    ContainerArchiveImageLoadFailedException,
    ContainerImagePullFailedException,
    ContainerInvalidSocketPathException,
)
from samcli.local.docker.platform_config import get_finch_registry_config_path, get_finch_socket_path

LOG = logging.getLogger(__name__)

# Prefix of the DockerException docker-py raises when a configured credential helper fails or is missing
CREDENTIALS_STORE_ERROR_PREFIX = "Credentials store error"

# Pull errors that usually mean the registry wanted credentials, or rate limited an anonymous pull.
# finch-daemon reports authorization failures as "not found". Status codes must stand alone so they
# do not match inside digests, sizes or ports.
REGISTRY_AUTH_FAILURE_PATTERN = re.compile(
    r"\b(?:401|403|404|429)\b|unauthorized|denied|not found|toomanyrequests|rate limit", re.IGNORECASE
)

# Maximum length of third-party error text (e.g. credential helper output) included in warnings
_MAX_ERROR_TEXT_IN_WARNING = 200

# Warnings about the user's registry setup are shown once per process, not once per client
_warned_once: Set[str] = set()
_warned_once_lock = threading.Lock()


def _warn_once(key: str, message: str, *args: Any) -> None:
    with _warned_once_lock:
        if key in _warned_once:
            return
        _warned_once.add(key)
    LOG.warning(message, *args)


class ContainerClient(docker.DockerClient, ABC):
    """
    Abstract base class for container clients that provides a unified interface
    for different container runtimes while inheriting from docker.DockerClient
    for full compatibility.

    This class implements the strategy pattern to handle runtime-specific behaviors
    while maintaining backward compatibility with existing code that expects
    docker.DockerClient instances.

    The class handles Docker client initialization by:
    1. Starting with system environment variables (os.environ)
    2. Applying any environment overrides passed by subclasses
    3. Processing the merged environment with Docker's kwargs_from_env()
    4. Overriding base_url if explicitly provided as a parameter
    5. Initializing DockerClient with the processed parameters

    Subclasses can call super().__init__(base_url=...) for explicit URL override
    """

    # Initialize socket_path
    socket_path: Optional[str] = None

    def __init__(self, base_url=None):
        """
        Initialize the container client with environment variable processing and overrides.

        This constructor implements the core environment variable processing logic:
        1. Starts with system environment variables (os.environ)
        2. Processes the environment using Docker's kwargs_from_env()
        3. Override the base_url if provide
        4. Initializes DockerClient with the processed parameters


        Args:
            base_url: Docker daemon URL (e.g., 'unix:///var/run/docker.sock', 'tcp://localhost:2375')
                    If provided, overrides the base_url from environment variables

        Example:
            # Uses environment variables and Docker's default connection
            client = ContainerClient()

            # Uses explicit base_url (overrides environment DOCKER_HOST)
            client = ContainerClient(base_url='unix:///var/run/docker.sock')
        """

        # Always start with environment variables
        current_env = os.environ.copy()
        self.client_params = kwargs_from_env(environment=current_env)

        # Override base_url if explicitly provided
        if base_url is not None:
            self.client_params["base_url"] = base_url

        # Specify minimum version
        self.client_params["version"] = os.environ.get(GlobalConfig.DOCKER_API_ENV_VAR, DOCKER_MIN_API_VERSION)

        # Initialize DockerClient with processed parameters
        LOG.debug(f"Creating container client with parameters: {self.client_params}")
        super().__init__(**self.client_params)

        # Registry credentials are resolved once per client, so every operation that talks to a
        # registry (pull, build, push) authenticates the same way for a given runtime.
        self._load_registry_auth_config()

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this client instance is available and can connect.

        This method tests actual connectivity by pinging the container runtime.
        It uses the inherited ping() method from docker.DockerClient to test
        if the container runtime is reachable and responding.

        Returns:
            bool: True if the client can successfully connect to the runtime
        """
        pass

    @abstractmethod
    def get_socket_path(self) -> str:
        """
        Return the socket path being used by this client.

        Returns:
            str: Socket path (e.g., 'unix:///var/run/docker.sock', 'unix://~/.finch/finch.sock')

        Raises:
            ContainerInvalidSocketPathException: When the socket path is invalid or inaccessible
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

    def warn_about_registry_credentials(self) -> None:
        """
        Warn about registry credential setups that make pulls silently anonymous.

        Called once the client has been selected as the runtime for the command, so users are not
        warned about a runtime they are not using. The default (Docker) has nothing to warn about.
        """

    def _load_registry_auth_config(self) -> None:
        """
        Load the registry credentials this runtime uses into the client.

        The default keeps docker-py's own resolution: the Docker client config
        (``$DOCKER_CONFIG`` or ``~/.docker/config.json``) and its credential helpers.
        Runtimes that keep registry credentials elsewhere override this.
        """

    def pull_image(self, repository: str, tag: Optional[str] = None) -> Iterator[Dict[str, Any]]:
        """
        Pull an image, yielding the runtime's progress events.

        A runtime can report a failed pull (e.g. a 429 rate limit or an authorization error) as an
        ``error`` event in an otherwise successful streamed response, instead of an HTTP error.
        Both cases raise ContainerImagePullFailedException, so a failed pull is never mistaken for a
        successful one that later surfaces as a misleading "no such image".

        Args:
            repository: Image repository, optionally including the tag
            tag: Image tag. If None, docker-py takes the tag from ``repository`` or uses ``latest``

        Returns:
            Iterator of progress events. The pull request is sent immediately; errors streamed
            by the runtime are raised while iterating.

        Raises:
            ContainerImagePullFailedException: If the runtime rejects or fails the pull
        """
        try:
            progress = self._request_pull(repository, tag)
        except docker.errors.APIError as ex:
            LOG.debug("Failed to pull image %s: %s", repository, ex)
            raise ContainerImagePullFailedException(self._describe_pull_failure(str(ex))) from ex
        return self._raise_on_streamed_pull_error(repository, progress)

    def pull_image_and_wait(self, image: str) -> None:
        """
        Pull an image and wait until the pull has finished, for callers that do not show progress.

        The pull only completes, and a failure reported by the runtime only surfaces, while the
        progress stream from ``pull_image`` is read, so this reads it to the end.

        Args:
            image: Image reference, e.g. ``public.ecr.aws/foo/bar:1.0`` (``latest`` when untagged)

        Raises:
            ContainerImagePullFailedException: If the runtime rejects or fails the pull
        """
        for _ in self.pull_image(image):
            pass

    def _request_pull(self, repository: str, tag: Optional[str]) -> Iterable[Any]:
        """
        Send the pull request, falling back to an anonymous pull when credentials cannot be read.

        docker-py raises "Credentials store error" when the config names a credential helper
        (``credsStore``/``credHelpers``) that is not installed, e.g. a ``"credsStore": "desktop"``
        left behind by an uninstalled Docker Desktop. Public images do not need credentials, so
        warn and pull anonymously instead of failing the command.
        """
        try:
            return cast(Iterable[Any], self.api.pull(repository, tag=tag, stream=True, decode=True))
        except docker.errors.APIError:
            raise
        except docker.errors.DockerException as ex:
            if not str(ex).startswith(CREDENTIALS_STORE_ERROR_PREFIX):
                raise
            _warn_once(
                "credentials-store-error",
                "Could not use the configured registry credential helper (%s). Pulling images without "
                "credentials; pulls from private registries will fail until the helper is installed or "
                "removed from the registry config.",
                str(ex)[:_MAX_ERROR_TEXT_IN_WARNING],
            )
            # An empty auth config sends an empty X-Registry-Auth header, i.e. an anonymous pull,
            # instead of resolving the broken credential helper again.
            return cast(Iterable[Any], self.api.pull(repository, tag=tag, stream=True, decode=True, auth_config={}))

    def _raise_on_streamed_pull_error(self, repository: str, progress: Iterable[Any]) -> Iterator[Dict[str, Any]]:
        for event in progress:
            if isinstance(event, dict) and event.get("error"):
                LOG.debug("Pull of image %s reported an error: %s", repository, event["error"])
                raise ContainerImagePullFailedException(self._describe_pull_failure(str(event["error"])))
            yield event

    def _describe_pull_failure(self, error: str) -> str:
        """
        Return the message for a failed pull. Runtimes override this to add setup guidance.
        """
        return error


class DockerContainerClient(ContainerClient):
    """
    Docker-specific container client implementation.

    This class provides Docker-specific implementations of container operations
    while maintaining full compatibility with the docker.DockerClient API.

    Usage:
        client = DockerContainerClient()
        client.images.list()  # Standard DockerClient API
        client.get_runtime_type()  # Returns "docker"
    """

    def __init__(self):
        """
        Initialize DockerContainerClient using Docker client parameters.

        Example:
            # Uses system environment variables
            client = DockerContainerClient()

            # Full DockerClient API available
            containers = client.containers.list()
            images = client.images.list()
        """
        socket_path = self.get_socket_path()

        if socket_path:
            LOG.debug(f"Creating Docker container client with base_url={socket_path}.")
            super().__init__(base_url=socket_path)
        else:
            LOG.debug("Creating Docker container client from environment variable.")
            super().__init__()

    def is_available(self):
        try:
            self.ping()
            return True
        except Exception as e:
            try:
                # docker engine > 29 requires 1.44 as minimum api version
                LOG.debug(f"Fall back docker api version to {DOCKER_MIN_API_VERSION_FALLBACK}: {e}")
                self.client_params["version"] = DOCKER_MIN_API_VERSION_FALLBACK
                self.api = docker.APIClient(**self.client_params)
                self.ping()
                LOG.debug(f"Docker daemon check succeeded with fallback: {e}")
                return True
            except Exception as e:
                LOG.debug(f"Docker daemon availability check failed with fallback: {e}")
                return False

    def get_runtime_type(self) -> str:
        """
        Return the runtime type identifier for Docker.

        Returns:
            str: Always returns "docker"
        """
        return "docker"

    def get_socket_path(self) -> str:
        """
        Return the socket path being used by this client.

        Returns:
            str: Socket path. Return empty string if DOCKER_HOST is not set.

        Raises:
            ContainerInvalidSocketPathException: When the socket path is set to Finch socket path.
        """
        # Explicitly use 'is not None' condition because self.socket_path = "" is a valid path
        if self.socket_path is not None:
            return self.socket_path

        # Explicitly use "" instead of None
        env_socket_path = os.environ.get("DOCKER_HOST", "")

        # Either str or None
        finch_socket_path = get_finch_socket_path()

        # Verify that DOCKER_HOST is not set to Finch socket path; The socket_path can be empty
        if env_socket_path and env_socket_path == finch_socket_path:
            raise ContainerInvalidSocketPathException(
                f"DOCKER_HOST is set to Finch socket path {finch_socket_path}! Abort creating Docker client."
            )

        self.socket_path = env_socket_path
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
        contain "Cannot locate specified Dockerfile" or "failed to read dockerfile" in the error message.

        Args:
            error: Exception or error message to check

        Returns:
            bool: True if the error indicates a dockerfile-related issue
        """
        patterns = ["Cannot locate specified Dockerfile", "failed to read dockerfile"]
        if isinstance(error, docker.errors.APIError):
            if not error.is_server_error:
                return False
            if not hasattr(error, "explanation") or error.explanation is None:
                return False
            return any(pattern in str(error.explanation) for pattern in patterns)
        elif isinstance(error, str):
            return any(pattern in error for pattern in patterns)
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
            LOG.debug(f"Image {image_id} not found, may have been already removed")
        except docker.errors.APIError as e:
            # Log but don't fail on cleanup errors
            LOG.warning(f"Failed to remove image {image_id}: {e}")

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
    overrides the base_url when creating client to connect to Finch daemon instead
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

        Args:
            base_url: Finch daemon URL (e.g., 'unix:///tmp/finch.sock')
                     If None, automatically detects the Finch socket path

        Example:
            # Automatically uses Finch socket if available
            client = FinchContainerClient()
        """

        socket_path = self.get_socket_path()
        if not socket_path:
            # If socket_path=None mean the platform does not support Finch. Do not create client
            return None

        LOG.debug(f"Creating Finch container client with base_url={socket_path}")
        super().__init__(base_url=socket_path)  # TODO: Placeholder until Finch updates to Docker's min latest version

    def is_available(self):
        try:
            self.ping()
            return True
        except Exception as e:
            LOG.debug(f"Finch daemon availability check failed: {e}")
            return False

    def get_socket_path(self) -> str:
        """
        Return the socket path being used by this Finch client.

        Returns:
            str: Socket path
        """
        if self.socket_path is not None:
            return self.socket_path

        finch_socket_path = get_finch_socket_path()
        if finch_socket_path is None:
            raise ContainerInvalidSocketPathException("Finch is not supported on current platform!")
        self.socket_path = finch_socket_path
        return self.socket_path

    def get_runtime_type(self) -> str:
        """
        Return the runtime type identifier for Finch.

        Returns:
            str: Always returns "finch"
        """
        return "finch"

    def _load_registry_auth_config(self) -> None:
        """
        Use the registry credentials ``finch login`` wrote.

        On macOS ``finch login`` writes ``~/.finch/config.json`` (or ``$DOCKER_CONFIG``), not the
        ``~/.docker/config.json`` docker-py reads, so without this every pull and build went out
        anonymously. docker-py sends the loaded config on pulls, builds and pushes. The Docker client
        config stays in use when the Finch config is missing, unusable or holds no credentials.
        On Linux ``finch login`` writes the Docker client config itself, so there is nothing to load.
        """
        self._uses_finch_registry_config = False
        config_path = get_finch_registry_config_path()
        if not config_path or not os.path.isfile(config_path):
            LOG.debug("No Finch registry config found; using the Docker client config.")
            return
        if not _is_registry_config_usable(config_path):
            return
        try:
            # Replaces the client's credential store only if the config parses
            self.api.reload_config(config_path)
        except (docker.errors.DockerException, ValueError) as ex:
            # e.g. an "auth" entry that is not valid base64
            _warn_once(
                f"unusable-registry-config:{config_path}",
                "Could not load registry config %s (%s); using the Docker client config instead.",
                config_path,
                str(ex)[:_MAX_ERROR_TEXT_IN_WARNING],
            )
            return
        LOG.debug("Using Finch registry config %s.", config_path)
        self._uses_finch_registry_config = True

    def warn_about_registry_credentials(self) -> None:
        """
        Warn when the Docker client config Finch relies on cannot be read by the current user.

        On Linux a ``finch login`` run as root (``sudo`` or a setuid ``finch``) before that config
        exists leaves it owned by root, and docker-py silently treats an unreadable config as missing.
        """
        if getattr(self, "_uses_finch_registry_config", False) or _is_docker_config_readable():
            return
        _warn_once(
            "unreadable-docker-config",
            "The registry credentials in %s cannot be read by the current user, so images are pulled "
            "without credentials and may be rate limited. This happens when `finch login` runs as root "
            "before that file exists. Run `finch login` without sudo, or give the file back to your "
            "user (sudo chown -R $USER %s).",
            _docker_config_file(),
            _docker_config_dir(),
        )

    def _describe_pull_failure(self, error: str) -> str:
        """
        Add Finch credential guidance when a pull failed in a way that points at registry sign-in.
        """
        if not REGISTRY_AUTH_FAILURE_PATTERN.search(error):
            return error
        finch_config_path = get_finch_registry_config_path()
        if getattr(self, "_uses_finch_registry_config", False) and finch_config_path:
            credentials_path = finch_config_path
        else:
            credentials_path = _docker_config_file()
        return (
            f"{error}\n"
            f"If the registry requires sign-in or limits anonymous pulls, run `finch login <registry>` "
            f"(on Linux, without sudo) and make sure {credentials_path} is readable by your user."
        )

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


def _docker_config_dir() -> str:
    """Directory of the Docker client config docker-py reads ($DOCKER_CONFIG or ~/.docker)."""
    return os.environ.get("DOCKER_CONFIG") or os.path.join(os.path.expanduser("~"), ".docker")


def _docker_config_file() -> str:
    return os.path.join(_docker_config_dir(), "config.json")


def _is_docker_config_readable() -> bool:
    """
    False when the Docker client config exists but the current user cannot read it.

    A missing config is "readable": docker-py simply has no credentials, which is expected.
    """
    config_dir = _docker_config_dir()
    if not os.path.isdir(config_dir):
        return True
    if not os.access(config_dir, os.R_OK | os.X_OK):
        return False
    config_file = _docker_config_file()
    return not os.path.isfile(config_file) or os.access(config_file, os.R_OK)


def _is_registry_config_usable(config_path: str) -> bool:
    """
    Whether docker-py can use a registry config without failing registry operations.

    docker-py fails every pull, build and push that resolves credentials through a credential helper
    (``credsStore``/``credHelpers``) that is not installed, and a build resolves all of them. Such a
    config, or one that is not a JSON object, is not used; the Docker client config stays in use.
    """
    try:
        with open(config_path) as config_file:
            config = json.load(config_file)
        if not isinstance(config, dict):
            raise ValueError("expected a JSON object")
    except (OSError, ValueError) as ex:
        _warn_once(
            f"unusable-registry-config:{config_path}",
            "Could not read registry config %s (%s); using the Docker client config instead.",
            config_path,
            str(ex)[:_MAX_ERROR_TEXT_IN_WARNING],
        )
        return False

    missing_helpers = _missing_credential_helpers(config)
    if missing_helpers:
        _warn_once(
            f"missing-credential-helpers:{config_path}",
            "Registry config %s uses credential helper(s) %s that are not installed, so it is not used and "
            "the Docker client config is used instead. Install the helper(s) or remove them from %s.",
            config_path,
            ", ".join(f"docker-credential-{helper}" for helper in missing_helpers),
            config_path,
        )
        return False
    return True


def _missing_credential_helpers(config: Dict[str, Any]) -> List[str]:
    """
    Credential helpers named by a registry config (``credsStore``/``credHelpers``) that are not installed.
    """
    helpers = set()
    if config.get("credsStore"):
        helpers.add(str(config["credsStore"]))
    if isinstance(config.get("credHelpers"), dict):
        helpers.update(str(helper) for helper in config["credHelpers"].values() if helper)
    return sorted(helper for helper in helpers if shutil.which(f"docker-credential-{helper}") is None)
