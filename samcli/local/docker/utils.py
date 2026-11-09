"""
Helper methods that aid interactions within docker containers.
"""

import errno
import logging
import os
import pathlib
import platform
import posixpath
import random
import re
import socket
from typing import Optional, Set

import docker

from samcli.lib.utils.architecture import ARM64, validate_architecture
from samcli.local.docker.container_client import ContainerClient
from samcli.local.docker.container_client_factory import ContainerClientFactory
from samcli.local.docker.exceptions import (
    NoFreePortsError,
)

LOG = logging.getLogger(__name__)

# Winsock's WSAEADDRNOTAVAIL. CPython's winerror_to_errno passes Winsock codes through
# unchanged, so this - not errno.EADDRNOTAVAIL - is what errno carries on Windows. The value
# is fixed by the Winsock ABI and the name is absent from errno on POSIX, so it is spelled
# out here to keep one set that is correct, and testable, on every platform.
WSAEADDRNOTAVAIL = 10049

# Errnos meaning the named address cannot be probed on THIS machine at all, as opposed to a
# port on it being busy. The answer is the same for every candidate port, so these short the
# scan instead of continuing it. EADDRNOTAVAIL (and its Winsock spelling) is the interface
# not existing here; EAFNOSUPPORT is the family being unavailable, which is what creating an
# AF_INET6 socket raises on a host booted with IPv6 disabled.
UNPROBEABLE_ERRNOS = frozenset({errno.EADDRNOTAVAIL, WSAEADDRNOTAVAIL, errno.EAFNOSUPPORT})

# Interfaces already reported as unprobeable. Whether an interface exists in this network
# namespace does not change while the process runs, but find_free_port is called once per
# container creation - every invoke in cold-container mode - so the warning is emitted once
# per interface instead of once per container. A duplicate from racing threads is harmless.
_UNPROBEABLE_INTERFACES: Set[str] = set()


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


def _unprobeable_port(network_interface: str, port: int) -> int:
    """
    Returns a port without probing it, warning once per interface.

    :return: int - the port passed in
    """
    if network_interface in _UNPROBEABLE_INTERFACES:
        LOG.debug("Using port %s on %s without checking it", port, network_interface)
    else:
        _UNPROBEABLE_INTERFACES.add(network_interface)
        LOG.warning(
            "Cannot check whether ports are free on %s: that address does not exist on this "
            "machine, probably because the container engine runs elsewhere. Using port %s "
            "without checking it; if that machine already has the port taken, the engine "
            "refuses the publish and the command fails naming that port. No action is needed "
            "when the container engine runs on another host or in another network namespace.",
            network_interface,
            port,
        )
    return port


def find_free_port(network_interface: str, start: int = 5000, end: int = 9000) -> int:
    """
    Utility function which scans through a port range in a randomized manner
    and finds the first free port a socket can bind to.

    The port is published by the container engine (Docker or Finch), which may run on a
    different host (or in a different network namespace) than SAM CLI itself. An address that
    does not exist here cannot be probed here: every candidate fails with EADDRNOTAVAIL, which
    would otherwise report the whole range as busy. In that case a port is returned unprobed,
    with a warning, and the engine's own bind decides whether it is actually free.

    :raises NoFreePortException if no free ports found in range.
    :return: int - free port
    """
    port_range = [random.randrange(start, end) for _ in range(start, end)]

    if network_interface:
        # Resolve a named or literal address once to pick the socket family, so that an IPv6
        # value binds on an IPv6 socket instead of failing resolution on an AF_INET one, and
        # so that a scope id (fe80::1%eth0) survives into the bind. Resolving once rather
        # than per candidate also keeps a value that does not resolve from costing a scan.
        try:
            family, socket_type, proto, _, sockaddr = socket.getaddrinfo(network_interface, 0, type=socket.SOCK_STREAM)[
                0
            ]
        except (OSError, ValueError):
            # socket.gaierror (an OSError subclass) for an address this machine cannot
            # resolve, and UnicodeError (a ValueError, NOT an OSError) when getaddrinfo's
            # idna encoding rejects the name - a label over 63 characters, which a mistyped
            # flag value can be. Same answer for every port, so there is nothing to scan.
            return _unprobeable_port(network_interface, port_range[0])
    else:
        # An empty interface means "all interfaces", and is probed on IPv4 - which is what
        # bind(("", port)) did before this function resolved anything, and the family the
        # engine publishes on by default.
        #
        # getaddrinfo(None, AI_PASSIVE) is deliberately NOT used to derive this. It returns
        # both wildcards and their ORDER IS PLATFORM-DEPENDENT: IPv4 first on Linux, IPv6
        # first on macOS. Taking the first entry therefore probes a different family per
        # platform, and on a platform whose stacks are separate (macOS defaults to
        # ip6.v6only=1) a bind on the IPv6 wildcard SUCCEEDS while the IPv4 wildcard is
        # already taken - reporting free a port the engine then cannot publish.
        family, socket_type, proto, sockaddr = socket.AF_INET, socket.SOCK_STREAM, 0, ("", 0)

    for port in port_range:
        try:
            LOG.debug("Checking free port on %s:%s", network_interface, port)
            with socket.socket(family, socket_type, proto) as s:
                s.bind((sockaddr[0], port) + tuple(sockaddr[2:]))
            return port
        except OSError as ex:
            if ex.errno in UNPROBEABLE_ERRNOS:
                return _unprobeable_port(network_interface, port)
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


def get_validated_container_client() -> ContainerClient:
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
