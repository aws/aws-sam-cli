"""
Hash calculation utilities for files and directories.
"""

import hashlib
import os
import sys
from typing import Any, List, Optional, cast

BLOCK_SIZE = 4096
# earliest python version to support usedforsecurity option for hashlib.md5 is 3.9
# https://docs.python.org/3/library/hashlib.html#hash-algorithms
_MAJOR_PYTHON_VERSION = 3
_MINOR_PYTHON_VERSION = 9


def _get_md5():
    if sys.version_info.major >= _MAJOR_PYTHON_VERSION and sys.version_info.minor >= _MINOR_PYTHON_VERSION:
        return hashlib.md5(usedforsecurity=False)
    else:
        return hashlib.md5()


def file_checksum(file_name: str, hash_generator: Any = None) -> str:
    """

    Parameters
    ----------
    file_name : str
        file name of the file for which md5 checksum is required.
    hash_generator : hashlib._Hash
        hashlib _Hash object for generating hashes. Defaults to hashlib.md5.

    Returns
    -------
    checksum of the given file.

    """
    # Default value is set here because default values are static mutable in Python
    if not hash_generator:
        hash_generator = _get_md5()
    with open(file_name, "rb") as file_handle:
        # Save current cursor position and reset cursor to start of file
        curpos = file_handle.tell()
        file_handle.seek(0)

        buf = file_handle.read(BLOCK_SIZE)
        while buf:
            hash_generator.update(buf)
            buf = file_handle.read(BLOCK_SIZE)

        # Restore file cursor's position
        file_handle.seek(curpos)

        return cast(str, hash_generator.hexdigest())


def dir_checksum(
    directory: str, followlinks: bool = True, ignore_list: Optional[List[str]] = None, hash_generator: Any = None
) -> str:
    """

    Parameters
    ----------
    directory : dict
        A directory with an absolute path
    followlinks : bool
        Follow symbolic links through the given directory
    ignore_list : list(str)
        The list of file/directory names to ignore in checksum
    hash_generator : hashlib._Hash
        The hashing method (hashlib _Hash object) that generates checksum. Defaults to hashlib.md5.

    Returns
    -------
    checksum hash of the directory.

    """
    ignore_set = set(ignore_list or [])
    if not hash_generator:
        hash_generator = _get_md5()
    files = list()
    # Walk through given directory and find all directories and files.
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=followlinks):
        # > When topdown is True, the caller can modify the dirnames list in-place
        # > (perhaps using del or slice assignment) and walk() will only recurse
        # > into the subdirectories whose names remain in dirnames
        # > https://docs.python.org/library/os.html#os.walk
        dirnames[:] = [dirname for dirname in dirnames if dirname not in ignore_set]
        # Go through every file in the directory and sub-directory.
        for filepath in [os.path.join(dirpath, filename) for filename in filenames if filename not in ignore_set]:
            # Look at filename and contents.
            # Encode file's checksum to be utf-8 and bytes.
            files.append(filepath)

    files.sort()
    for file in files:
        hash_generator.update(os.path.relpath(file, directory).encode("utf-8"))
        filepath_checksum = file_checksum(file)
        hash_generator.update(filepath_checksum.encode("utf-8"))

    return cast(str, hash_generator.hexdigest())


def str_checksum(content: str, hash_generator: Any = None) -> str:
    """
    return a md5 checksum of a given string

    Parameters
    ----------
    content: string
        the string to be hashed
     hash_generator : hashlib._Hash
        The hashing method (hashlib _Hash object) that generates checksum. Defaults to hashlib.md5.
    Returns
    -------
    md5 checksum of content
    """
    if not hash_generator:
        hash_generator = _get_md5()
    hash_generator.update(content.encode("utf-8"))
    return cast(str, hash_generator.hexdigest())
