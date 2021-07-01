"""
Hash calculation utilities for files and directories.
"""
import os
import hashlib
from typing import List, Optional

BLOCK_SIZE = 4096


def file_checksum(file_name: str) -> str:
    """

    Parameters
    ----------
    file_name: file name of the file for which md5 checksum is required.

    Returns
    -------
    md5 checksum of the given file.

    """
    with open(file_name, "rb") as file_handle:
        md5 = hashlib.md5()

        # Save current cursor position and reset cursor to start of file
        curpos = file_handle.tell()
        file_handle.seek(0)

        buf = file_handle.read(BLOCK_SIZE)
        while buf:
            md5.update(buf)
            buf = file_handle.read(BLOCK_SIZE)

        # Restore file cursor's position
        file_handle.seek(curpos)

        return md5.hexdigest()


def dir_checksum(directory: str, followlinks: bool = True, ignore_list: Optional[List[str]] = None) -> str:
    """

    Parameters
    ----------
    directory : A directory with an absolute path
    followlinks: Follow symbolic links through the given directory
    ignore_list: The list of file/directory names to ignore in checksum

    Returns
    -------
    md5 checksum of the directory.

    """
    ignore_set = set(ignore_list or [])
    md5_dir = hashlib.md5()
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
