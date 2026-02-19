"""
Build client abstraction for container image builds.

This module provides an abstract interface for building container images,
allowing different implementations (SDK-based or CLI-based) to be used
interchangeably.
"""

import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional, Tuple

import docker.errors

from samcli.local.docker.container_client import ContainerClient

LOG = logging.getLogger(__name__)


class ImageBuildClient(ABC):
    """
    Abstract interface for building container images.

    Implementations can use different methods (SDK via docker-py, or CLI via
    docker/finch commands) while providing a consistent interface for building
    Lambda function images.
    """

    @abstractmethod
    def build_image(
        self,
        path: str,
        dockerfile: str,
        tag: str,
        buildargs: Optional[Dict[str, str]] = None,
        platform: Optional[str] = None,
        target: Optional[str] = None,
        rm: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Build a container image from a Dockerfile.

        Parameters
        ----------
        path : str
            Path to the build context directory
        dockerfile : str
            Path to the Dockerfile (relative to context or absolute)
        tag : str
            Tag for the built image (e.g., "myfunction:latest")
        buildargs : dict, optional
            Build arguments to pass (e.g., {"ARG_NAME": "value"})
        platform : str, optional
            Target platform (e.g., "linux/amd64", "linux/arm64")
        target : str, optional
            Build target stage in multi-stage Dockerfile
        rm : bool
            Remove intermediate containers after build (default: True)

        Yields
        ------
        dict
            Build log entries with keys like 'stream', 'error', 'status'.
            Format matches docker-py SDK output.

        Raises
        ------
        Exception
            If build fails
        """
        pass

    @staticmethod
    @abstractmethod
    def is_available(engine_type: str) -> Tuple[bool, Optional[str]]:
        """
        Check if this build method is available for the given container engine.

        This method is called before creating a ImageBuildClient instance to validate
        that the necessary tools (CLI, plugins, etc.) are available.

        Parameters
        ----------
        engine_type : str
            Container engine type: "docker" or "finch"

        Returns
        -------
        tuple[bool, Optional[str]]
            - (True, None) if the build method is available
            - (False, "error message") if not available

        Examples
        --------
        >>> CLIBuildClient.is_available("docker")
        (True, None)

        >>> CLIBuildClient.is_available("docker")
        (False, "docker buildx plugin not found")
        """
        pass


class SDKBuildClient(ImageBuildClient):
    """Build client using docker-py SDK."""

    def __init__(self, container_client: ContainerClient):
        self.container_client = container_client

    def build_image(
        self,
        path: str,
        dockerfile: str,
        tag: str,
        buildargs: Optional[Dict[str, str]] = None,
        platform: Optional[str] = None,
        target: Optional[str] = None,
        rm: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        """Build image using docker-py SDK"""
        build_kwargs = {
            "path": path,
            "dockerfile": dockerfile,
            "tag": tag,
            "rm": rm,
        }

        if buildargs is not None:
            build_kwargs["buildargs"] = buildargs
        if platform is not None:
            build_kwargs["platform"] = platform
        if target is not None:
            build_kwargs["target"] = target

        _, build_logs = self.container_client.images.build(**build_kwargs)
        return build_logs  # type: ignore[no-any-return]

    @staticmethod
    def is_available(engine_type: str) -> Tuple[bool, Optional[str]]:
        return (True, None)


class CLIBuildClient(ImageBuildClient):
    """Build client using docker/finch CLI commands."""

    def __init__(self, engine_type: str):
        self.engine_type = engine_type
        self.cli_command = engine_type

    def build_image(
        self,
        path: str,
        dockerfile: str,
        tag: str,
        buildargs: Optional[Dict[str, str]] = None,
        platform: Optional[str] = None,
        target: Optional[str] = None,
        rm: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        # Make dockerfile path relative to context if not absolute
        if not os.path.isabs(dockerfile):
            dockerfile = os.path.join(path, dockerfile)

        cmd = [self.cli_command]

        if self.engine_type == "docker":
            cmd.append("buildx")

        cmd.extend(["build", "-f", dockerfile, "-t", tag])

        if self.engine_type == "docker":
            cmd.extend(["--provenance=false", "--sbom=false"])

        if platform:
            cmd.extend(["--platform", platform])

        if buildargs:
            for k, v in buildargs.items():
                cmd.extend(["--build-arg", f"{k}={v}"])

        if target:
            cmd.extend(["--target", target])

        if rm:
            cmd.append("--rm")

        cmd.append(path)

        LOG.debug(f"Executing build command: {' '.join(cmd)}")

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        build_log = []
        if process.stdout:
            for line in process.stdout:
                build_log.append(line)
                yield {"stream": line}

        process.wait()

        if process.returncode != 0:
            raise docker.errors.BuildError(f"Build failed with exit code {process.returncode}", "".join(build_log))

    @staticmethod
    def is_available(engine_type: str) -> Tuple[bool, Optional[str]]:
        if engine_type == "docker":
            if not shutil.which("docker"):
                return (False, "Docker CLI not found")

            result = subprocess.run(
                ["docker", "buildx", "version"],
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                return (False, "docker buildx plugin not available")

            return (True, None)

        elif engine_type == "finch":
            if not shutil.which("finch"):
                return (False, "Finch CLI not found")

            result = subprocess.run(
                ["finch", "version"],
                capture_output=True,
                check=False,
            )

            if result.returncode != 0:
                return (False, "finch CLI not working")

            return (True, None)

        return (False, f"Unknown engine type: {engine_type}")
