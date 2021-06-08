"""
Hash calculation utilities for files and directories.
"""
import os
import hashlib
from typing import Any, cast

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


def dir_checksum(directory: str, followlinks: bool = True) -> str:
    """

    Parameters
    ----------
    directory : A directory with an absolute path
    followlinks: Follow symbolic links through the given directory

    Returns
    -------
    md5 checksum of the directory.

    """
    md5_dir = hashlib.md5()
    files = list()
    # Walk through given directory and find all directories and files.
    for dirpath, _, filenames in os.walk(directory, followlinks=followlinks):
        # Go through every file in the directory and sub-directory.
        for filepath in [os.path.join(dirpath, filename) for filename in filenames]:
            # Look at filename and contents.
            # Encode file's checksum to be utf-8 and bytes.
            files.append(filepath)

    files.sort()
    for file in files:
        md5_dir.update(os.path.relpath(file, directory).encode("utf-8"))
        filepath_checksum = file_checksum(file)
        md5_dir.update(filepath_checksum.encode("utf-8"))

    return md5_dir.hexdigest()


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
