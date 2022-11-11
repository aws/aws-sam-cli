"""
Common Path related utilities
"""
from pathlib import PureWindowsPath


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
