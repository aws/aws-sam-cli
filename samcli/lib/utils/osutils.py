"""
Common OS utilities
"""

import io
import logging
import os
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Union, cast

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


def stdout() -> io.TextIOWrapper:
    """
    Returns the stdout as a byte stream in a Py2/PY3 compatible manner

    Returns
    -------
    io.BytesIO
        Byte stream of Stdout
    """
    # ensure stdout is utf8

    stdout_text_io = cast(io.TextIOWrapper, sys.stdout)
    stdout_text_io.reconfigure(encoding="utf-8")

    return stdout_text_io


def stderr() -> io.TextIOWrapper:
    """
    Returns the stderr as a byte stream in a Py2/PY3 compatible manner

    Returns
    -------
    io.BytesIO
        Byte stream of stderr
    """
    # ensure stderr is utf8
    stderr_text_io = cast(io.TextIOWrapper, sys.stderr)
    stderr_text_io.reconfigure(encoding="utf-8")

    return stderr_text_io


def remove(path):
    if path:
        try:
            Path(path).unlink(missing_ok=True)
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


def copytree(source, destination, ignore=None):
    """
    Recursively copy a directory tree from source to destination, allowing the destination
    to already exist. Symbolic links in the source tree are preserved as symbolic links
    in the destination.

    Delegates to ``shutil.copytree`` with ``dirs_exist_ok=True`` and ``symlinks=True``.

    :type source: str
    :param source:
        Path to the source directory to copy
    :type destination: str
    :param destination:
        Path to the destination directory. Will be created if it does not exist;
        existing files will be overwritten by corresponding files from source.
    :type ignore: callable, optional
    :param ignore:
        A callable that receives the directory being visited and a list of its contents,
        and returns a set of names to ignore. See ``shutil.ignore_patterns`` for a helper.
    """
    shutil.copytree(source, destination, symlinks=True, ignore=ignore, dirs_exist_ok=True)


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


def create_symlink_or_copy(source: str, destination: str) -> None:
    """Tries to create symlink, if it fails it will copy source into destination"""
    LOG.debug("Creating symlink; source: %s, destination: %s", source, destination)
    try:
        os.symlink(Path(source).absolute(), Path(destination).absolute())
    except OSError as ex:
        LOG.warning(
            "Symlink operation is failed, falling back to copying files",
            exc_info=ex if LOG.isEnabledFor(logging.DEBUG) else None,
        )
        copytree(source, destination)
