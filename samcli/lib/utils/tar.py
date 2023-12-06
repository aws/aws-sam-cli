"""
Tarball Archive utility
"""

import logging
import os
import tarfile
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryFile
from typing import IO, Callable, Dict, List, Optional, Union

LOG = logging.getLogger(__name__)


@contextmanager
def create_tarball(
    tar_paths: Dict[Union[str, Path], str],
    tar_filter: Optional[Callable[[tarfile.TarInfo], Union[None, tarfile.TarInfo]]] = None,
    mode: str = "w",
    dereference: bool = False,
):
    """
    Context Manger that creates the tarball of the Docker Context to use for building the image

    Parameters
    ----------
    tar_paths: Dict[Union[str, Path], str]
        Key representing a full path to the file or directory and the Value representing the path within the tarball
    tar_filter: Optional[Callable[[tarfile.TarInfo], Union[None, tarfile.TarInfo]]]
        A method that modifies the tar file entry before adding it to the archive. Default to `None`
    mode: str
        The mode in which the tarfile is opened. Defaults to "w".
    dereference: bool
        Pass `True` to resolve symlinks before adding to archive. Otherwise, adds the symlink itself to the archive

    Yields
    ------
    IO
        The tarball file
    """
    tarballfile = TemporaryFile()

    do_dereferece = dereference

    # validate that the destinations for the symlink targets exist
    if do_dereferece and not _validate_destinations_exists(list(tar_paths.keys())):
        LOG.warning("Falling back to not resolving symlinks to create a tarball.")
        do_dereferece = False

    with tarfile.open(fileobj=tarballfile, mode=mode, dereference=do_dereferece) as archive:
        for path_on_system, path_in_tarball in tar_paths.items():
            archive.add(path_on_system, arcname=path_in_tarball, filter=tar_filter)

    # Flush are seek to the beginning of the file
    tarballfile.flush()
    tarballfile.seek(0)

    try:
        yield tarballfile
    finally:
        tarballfile.close()


def _validate_destinations_exists(tar_paths: Union[List[Union[str, Path]], List[Path]]) -> bool:
    """
    Validates whether the destination of a symlink exists by resolving the link
    and checking the resolved path.

    Parameters
    ----------
    tar_paths: List[Union[str, Path]]
        A list of Paths to check

    Return
    ------
    bool:
        True all the checked paths exist, otherwise returns false
    """
    for file in tar_paths:
        file_path_obj = Path(file)

        try:
            resolved_path = file_path_obj.resolve()
        except OSError:
            # this exception will occur on Windows and will return
            # a WinError 123
            LOG.warning(f"Failed to resolve file {file_path_obj} on the host machine")
            return False

        if file_path_obj.is_dir():
            # recursively call this method to validate the children are not symlinks to empty locations
            children = list(file_path_obj.iterdir())
            if not _validate_destinations_exists(children):
                # exits early
                return False
        elif file_path_obj.is_symlink() and not resolved_path.exists():
            LOG.warning(f"Symlinked file {file_path_obj} -> {resolved_path} does not exist!")
            return False

    return True


def _is_within_directory(directory: Union[str, os.PathLike], target: Union[str, os.PathLike]) -> bool:
    """Checks if target is located under directory"""
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)

    prefix = os.path.commonprefix([abs_directory, abs_target])

    return bool(prefix == abs_directory)


def extract_tarfile(
    tarfile_path: Union[str, os.PathLike] = "",
    file_obj: Optional[IO[bytes]] = None,
    unpack_dir: Union[str, os.PathLike] = "",
) -> None:
    """
    Extracts a tarfile using the provided parameters. If file_obj is specified,
    it is used instead of the file_obj opened for tarfile_path.

    Parameters
    ----------
    tarfile_path Union[str, os.PathLike]
        Key representing a full path to the file or directory and the Value representing the path within the tarball

    file_obj Optional[IO[bytes]]
        Object for the tarfile that will be extracted

    unpack_dir Union[str, os.PathLike]
        The directory where the tarfile members will be extracted.
    """
    with tarfile.open(name=tarfile_path, fileobj=file_obj, mode="r") as tar:
        # Makes sure the tar file is sanitized and is free of directory traversal vulnerability
        # See: https://github.com/advisories/GHSA-gw9q-c7gh-j9vm
        for member in tar.getmembers():
            member_path = os.path.join(unpack_dir, member.name)
            if not _is_within_directory(unpack_dir, member_path):
                raise tarfile.ExtractError("Attempted Path Traversal in Tar File")

        tar.extractall(unpack_dir)
