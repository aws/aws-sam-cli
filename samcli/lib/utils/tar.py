"""
Tarball Archive utility
"""

import os
import tarfile
from contextlib import contextmanager
from tempfile import TemporaryFile
from typing import IO, Optional, Union


@contextmanager
def create_tarball(tar_paths, tar_filter=None, mode="w"):
    """
    Context Manger that creates the tarball of the Docker Context to use for building the image

    Parameters
    ----------
    tar_paths dict(str, str)
        Key representing a full path to the file or directory and the Value representing the path within the tarball

    mode str
        The mode in which the tarfile is opened. Defaults to "w".

    Yields
    ------
    IO
        The tarball file
    """
    tarballfile = TemporaryFile()

    with tarfile.open(fileobj=tarballfile, mode=mode) as archive:
        for path_on_system, path_in_tarball in tar_paths.items():
            archive.add(path_on_system, arcname=path_in_tarball, filter=tar_filter)

    # Flush are seek to the beginning of the file
    tarballfile.flush()
    tarballfile.seek(0)

    try:
        yield tarballfile
    finally:
        tarballfile.close()


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
