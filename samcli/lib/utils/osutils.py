"""
Common OS utilities
"""
import logging
import os
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Union

LOG = logging.getLogger(__name__)

# Build directories need not be world writable.
# This is usually a optimal permission for directories
BUILD_DIR_PERMISSIONS = 0o755


@contextmanager
def mkdir_temp(mode=0o755, ignore_errors=False):
    """
    Context manager that makes a temporary directory and yields it name. Directory is deleted
    after the context exits

    Parameters
    ----------
    mode : octal
        Permissions to apply to the directory. Defaults to '755' because don't want directories world writable

    ignore_errors : boolean
        If true, we will log a debug statement on failure to clean up the temp directory, rather than failing.
        Defaults to False

    Yields
    -------
    str
        Path to the directory

    """

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        os.chmod(temp_dir, mode)

        yield temp_dir

    finally:
        if temp_dir:
            if ignore_errors:
                shutil.rmtree(temp_dir, False, rmtree_callback)
            else:
                shutil.rmtree(temp_dir)


def rmtree_callback(function, path, excinfo):
    """
    Callback function for shutil.rmtree to change permissions on the file path, so that
    it's delete-able incase the file path is read-only.
    :param function: platform and implementation dependent function.
    :param path: argument to the function that caused it to fail.
    :param excinfo: tuple returned by sys.exc_info()
    """
    try:
        os.chmod(path=path, mode=stat.S_IWRITE)
        os.remove(path)
    except OSError:
        LOG.debug("rmtree failed in %s for %s, details: %s", function, path, excinfo)


def rmtree_if_exists(path: Union[str, Path]):
    """Removes given path if the path exists"""
    path_obj = Path(str(path))
    if path_obj.exists():
        LOG.debug("Cleaning up path %s", str(path))
        shutil.rmtree(path_obj)


def stdout():
    """
    Returns the stdout as a byte stream in a Py2/PY3 compatible manner

    Returns
    -------
    io.BytesIO
        Byte stream of Stdout
    """
    return sys.stdout.buffer


def stderr():
    """
    Returns the stderr as a byte stream in a Py2/PY3 compatible manner

    Returns
    -------
    io.BytesIO
        Byte stream of stderr
    """
    return sys.stderr.buffer


def remove(path):
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


@contextmanager
def tempfile_platform_independent():
    # NOTE(TheSriram): Setting delete=False is specific to windows.
    # https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    _tempfile = tempfile.NamedTemporaryFile(delete=False)
    try:
        yield _tempfile
    finally:
        _tempfile.close()
        remove(_tempfile.name)


# NOTE: Py3.8 or higher has a ``dir_exist_ok=True`` parameter to provide this functionality.
#       This method can be removed if we stop supporting Py37
def copytree(source, destination, ignore=None):
    """
    Similar to shutil.copytree except that it removes the limitation that the destination directory should
    be present.
    :type source: str
    :param source:
        Path to the source folder to copy
    :type destination: str
    :param destination:
        Path to destination folder
    :type ignore: function
    :param ignore:
        A function that returns a set of file names to ignore, given a list of available file names. Similar to the
        ``ignore`` property of ``shutils.copytree`` method
    """

    if not os.path.exists(destination):
        os.makedirs(destination)

        try:
            # Let's try to copy the directory metadata from source to destination
            shutil.copystat(source, destination)
        except OSError as ex:
            # Can't copy file access times in Windows
            LOG.debug("Unable to copy file access times from %s to %s", source, destination, exc_info=ex)

    names = os.listdir(source)
    if ignore is not None:
        ignored_names = ignore(source, names)
    else:
        ignored_names = set()

    for name in names:
        # Skip ignored names
        if name in ignored_names:
            continue

        new_source = os.path.join(source, name)
        new_destination = os.path.join(destination, name)

        if os.path.isdir(new_source):
            copytree(new_source, new_destination, ignore=ignore)
        else:
            shutil.copy2(new_source, new_destination)


def convert_files_to_unix_line_endings(path: str, target_files: Optional[List[str]] = None) -> None:
    for subdirectory, _, files in os.walk(path):
        for file in files:
            if target_files is not None and file not in target_files:
                continue

            file_path = os.path.join(subdirectory, file)
            convert_to_unix_line_ending(file_path)


def convert_to_unix_line_ending(file_path: str) -> None:
    with open(file_path, "rb") as file:
        content = file.read()
    content = content.replace(b"\r\n", b"\n")
    with open(file_path, "wb") as file:
        file.write(content)
