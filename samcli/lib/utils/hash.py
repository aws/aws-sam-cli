"""
Hash calculation utilities for files and directories.
"""
import os
import hashlib
from typing import Any, cast, List, Optional

BLOCK_SIZE = 4096


def file_checksum(file_name: str, hash_generator: Any = None) -> str:
    """

    Parameters
    ----------
    file_name: file name of the file for which md5 checksum is required.

    hash_generator: hashlib _Hash object for generating hashes. Defaults to hashlib.md5.

    Returns
    -------
    checksum of the given file.

    """
    # Default value is set here because default values are static mutable in Python
    if not hash_generator:
        hash_generator = hashlib.md5()
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
    directory : A directory with an absolute path
    followlinks: Follow symbolic links through the given directory
    ignore_list: The list of file/directory names to ignore in checksum
    hash_generator: The hashing method (hashlib _Hash object) that generates checksum. Defaults to hashlib.md5.

    Returns
    -------
    checksum hash of the directory.

    """
    ignore_set = set(ignore_list or [])
    if not hash_generator:
        hash_generator = hashlib.md5()
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


def str_checksum(content: str) -> str:
    """
    return a md5 checksum of a given string

    Parameters
    ----------
    content: string
        the string to be hashed
    Returns
    -------
    md5 checksum of content
    """
    md5 = hashlib.md5()
    md5.update(content.encode("utf-8"))
    return md5.hexdigest()
