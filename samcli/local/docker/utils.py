"""
Helper methods that aid interactions within docker containers.
"""

import logging
import os
import pathlib
import platform
import posixpath
import random
import re
import socket
from typing import Optional

import docker

from samcli.lib.utils.architecture import ARM64, validate_architecture
from samcli.local.docker.container_client_factory import ContainerClientFactory
from samcli.local.docker.exceptions import (
    NoFreePortsError,
)

LOG = logging.getLogger(__name__)


def to_posix_path(code_path):
    """
    Change the code_path to be of unix-style if running on windows when supplied with an absolute windows path.

    Parameters
    ----------
    code_path : str
        Directory in the host operating system that should be mounted within the container.
    Returns
    -------
    str
        Posix equivalent of absolute windows style path.
    Examples
    --------
    >>> to_posix_path('/Users/UserName/sam-app')
    /Users/UserName/sam-app
    >>> to_posix_path('C:\\\\Users\\\\UserName\\\\AppData\\\\Local\\\\Temp\\\\mydir')
    /c/Users/UserName/AppData/Local/Temp/mydir
    """

    return (
        re.sub(
            "^([A-Za-z])+:",
            lambda match: posixpath.sep + match.group().replace(":", "").lower(),
            pathlib.PureWindowsPath(code_path).as_posix(),
        )
        if os.name == "nt"
        else code_path
    )


def find_free_port(network_interface: str, start: int = 5000, end: int = 9000) -> int:
    """
    Utility function which scans through a port range in a randomized manner
    and finds the first free port a socket can bind to.
    :raises NoFreePortException if no free ports found in range.
    :return: int - free port
    """
    port_range = [random.randrange(start, end) for _ in range(start, end)]
    for port in port_range:
        try:
            LOG.debug("Checking free port on %s:%s", network_interface, port)
            s = socket.socket()
            s.bind((network_interface, port))
            s.close()
            return port
        except OSError:
            continue
    raise NoFreePortsError(f"No free ports on the host machine from {start} to {end}")


def get_rapid_name(architecture: str) -> str:
    """
    Return the name of the rapid binary to use for an architecture

    Parameters
    ----------
    architecture : str
        Architecture

    Returns
    -------
    str
        "aws-lambda-rie-" + architecture
    """
    validate_architecture(architecture)

    return "aws-lambda-rie-" + architecture


def get_image_arch(architecture: str) -> str:
    """
    Returns the docker image architecture value corresponding to the
    Lambda architecture value

    Parameters
    ----------
    architecture : str
        Lambda architecture

    Returns
    -------
    str
        Docker image architecture
    """
    validate_architecture(architecture)

    return "arm64" if architecture == ARM64 else "amd64"


def get_docker_platform(architecture: str) -> str:
    """
    Returns the platform to pass to the docker client for a given architecture

    Parameters
    ----------
    architecture : str
        Architecture

    Returns
    -------
    str
        linux/arm64 for arm64, linux/amd64 otherwise
    """
    validate_architecture(architecture)

    return f"linux/{get_image_arch(architecture)}"


def get_validated_container_client():
    """
    Get validated container client using strategy pattern.
    """
    return ContainerClientFactory.create_client()


def get_tar_filter_for_windows():
    """
    Get tar filter function for Windows compatibility.

    Sets permission for all files in the tarball to 500 (Read and Execute Only).
    This is needed for systems without unix-like permission bits (Windows) while creating a unix image.
    Without setting this explicitly, tar will default the permission to 666 which gives no execute permission.

    Returns
    -------
    callable or None
        Filter function for Windows, None for Unix systems
    """

    def set_item_permission(tar_info):
        tar_info.mode = 0o500
        return tar_info

    return set_item_permission if platform.system().lower() == "windows" else None


def is_image_current(docker_client: docker.DockerClient, image_name: str) -> bool:
    """
    Check if local image is up-to-date with remote by comparing digests.

    Parameters
    ----------
    docker_client : docker.DockerClient
        Docker client instance
    image_name : str
        Name of the image to check

    Returns
    -------
    bool
        True if local image digest matches remote image digest
    """
    local_digest = get_local_image_digest(docker_client, image_name)
    remote_digest = get_remote_image_digest(docker_client, image_name)
    return local_digest is not None and local_digest == remote_digest


def get_local_image_digest(docker_client: docker.DockerClient, image_name: str) -> Optional[str]:
    """
    Get the digest of the local image.

    Parameters
    ----------
    docker_client : docker.DockerClient
        Docker client instance
    image_name : str
        Name of the image to get the digest

    Returns
    -------
    Optional[str]
        Image digest including 'sha256:' prefix, or None if not found
    """
    try:
        image_info = docker_client.images.get(image_name)
        full_digest = image_info.attrs.get("RepoDigests", [None])[0]
        return full_digest.split("@")[1] if full_digest else None
    except (AttributeError, IndexError, docker.errors.ImageNotFound):
        return None


def get_remote_image_digest(docker_client: docker.DockerClient, image_name: str) -> Optional[str]:
    """
    Get the digest of the remote image.

    Parameters
    ----------
    docker_client : docker.DockerClient
        Docker client instance
    image_name : str
        Name of the image to get the digest

    Returns
    -------
    Optional[str]
        Image digest including 'sha256:' prefix, or None if not found
    """
    try:
        remote_info = docker_client.images.get_registry_data(image_name)
        digest: Optional[str] = remote_info.attrs.get("Descriptor", {}).get("digest")
        return digest
    except Exception:
        return None
