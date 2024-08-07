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

import docker
import requests

from samcli.lib.utils.architecture import ARM64, validate_architecture
from samcli.local.docker.exceptions import NoFreePortsError

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


def is_docker_reachable(docker_client):
    """
    Checks if Docker daemon is running.

    :param docker_client : docker.from_env() - docker client object
    :returns True, if Docker is available, False otherwise.
    """
    errors = (docker.errors.APIError, requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout)
    if platform.system() == "Windows":
        import pywintypes  # pylint: disable=import-error

        errors += (pywintypes.error,)

    try:
        docker_client.ping()
        return True

    # When Docker is not installed, a request.exceptions.ConnectionError is thrown.
    # and also windows-specific errors
    except errors:
        LOG.debug("Docker is not reachable", exc_info=True)
        return False


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
