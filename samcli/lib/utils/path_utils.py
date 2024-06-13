"""
Common Path related utilities
"""

import logging
import os
from pathlib import PureWindowsPath

LOG = logging.getLogger(__name__)


def convert_path_to_unix_path(path: str) -> str:
    """
    Convert a path to a unix format path if it is windows, and leave it as is if it in a unix format.
    Parameters
    ----------
    path: str
        the path to be converted

    Returns
    -------
    str
        the path in unix format
    """
    return PureWindowsPath(path).as_posix()


def check_path_valid_type(path) -> bool:
    """
    Checks the input to see if is a valid type to be a path, returning false if otherwise
    Parameters
    ----------
    path: str
        the path to be checked

    Returns
    -------
    bool
        if the input is a valid path type
    """
    if isinstance(path, (bytes, str, os.PathLike, int)):
        return True
    LOG.debug("Type error when trying to use input {} as Path, not string, int, bytes or os.PathLike ".format(path))
    return False
