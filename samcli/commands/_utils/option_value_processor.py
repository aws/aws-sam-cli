"""
Parsing utilities commonly used to process information for commands
"""
import logging
import re
import sys
from typing import Optional, Dict, Tuple

from samcli.commands.exceptions import InvalidImageException, InvalidMountedPathException

LOG = logging.getLogger(__name__)


def process_env_var(container_env_var: Optional[Tuple[str]]) -> Dict:
    """
    Parameters
    ----------
    container_env_var : Tuple
        the tuple of command line env vars received from --container-env-var flag
        Each input format needs to be either function specific format (FuncName.VarName=Value)
        or global format (VarName=Value)

    Returns
    -------
    dictionary
        Processed command line environment variables
    """
    processed_env_vars: Dict = {}

    if container_env_var:
        for env_var in container_env_var:
            location_key = "Parameters"

            env_var_name, value = _parse_key_value_pair(env_var)

            if not env_var_name or not value:
                LOG.error("Invalid command line --container-env-var input %s, skipped", env_var)
                continue

            if "." in env_var_name:
                location_key, env_var_name = env_var_name.split(".", 1)
                if not location_key.strip() or not env_var_name.strip():
                    LOG.error("Invalid command line --container-env-var input %s, skipped", env_var)
                    continue

            if not processed_env_vars.get(location_key):
                processed_env_vars[location_key] = {}
            processed_env_vars[location_key][env_var_name] = value

    return processed_env_vars


def process_image_options(image_args: Optional[Tuple[str]]) -> Dict:
    """
    Parameters
    ----------
    image_args : Tuple
        Tuple of command line image options in the format of
        "Function1=public.ecr.aws/abc/abc:latest" or
        "public.ecr.aws/abc/abc:latest"

    Returns
    -------
    dictionary
        Function as key and the corresponding image URI as value.
        Global default image URI is contained in the None key.
    """
    images: Dict[Optional[str], str] = dict()
    if image_args:
        for image_string in image_args:
            function_name, image_uri = _parse_key_value_pair(image_string)
            if not image_uri:
                raise InvalidImageException(f"Invalid command line image input {image_string}.")
            images[function_name] = image_uri

    return images


def process_dir_mounts(container_dir_mount: Optional[Tuple[str]]) -> Dict:
    """
    Parameters
    ----------
    container_dir_mount : Tuple
        The tuple of command line args received from --container-dir-mount flag
        Tuples should be formatted like: /host/dir/to/mount:/container/mount/destination

    Returns
    -------
    dictionary
        {
           "/host/dir1": "/container/destination1",
           "/host/dir2": "/container/destination2"
        }
    """

    processed_dir_mounts: Dict = {}

    if container_dir_mount:
        for dir_mount in container_dir_mount:
            if ":" in dir_mount:
                host_dir, container_dir = dir_mount.rsplit(":", 1)
                # Host path is validated for current platform
                host_dir_valid = _validate_directory_path(host_dir, platform=sys.platform)
                # Container path is always a Linux path
                container_dir_valid = _validate_directory_path(container_dir, platform="linux")
                if host_dir_valid and container_dir_valid:
                    processed_dir_mounts[host_dir] = container_dir
                    continue
            msg = f"Invalid command line --container-dir-mount input {dir_mount}."
            raise InvalidMountedPathException(msg)

    return processed_dir_mounts


def _parse_key_value_pair(arg: str) -> Tuple[Optional[str], str]:
    """
    Parameters
    ----------
    arg : str
        Arg in the format of "Value" or "Key=Value"
    Returns
    -------
    key : Optional[str]
        If key is not specified, None will be the key.
    value : str
    """
    key: Optional[str]
    value: str
    if "=" in arg:
        parts = arg.split("=", 1)
        key = parts[0].strip()
        value = parts[1].strip()
    else:
        key = None
        value = arg.strip()
    return key, value


def _validate_directory_path(dir_path, platform) -> bool:
    regex_linux_macos = r"^(/[^/ ]*)+/?$"
    regex_windows = r'^[a-zA-Z]:[/\\](((?![<>:"/\\|?*]).)+((?<![ .])[/\\])?)*$'

    regex = regex_windows if platform == "win32" else regex_linux_macos
    return bool(re.match(regex, dir_path))
