"""
Tarball Archive utility
"""

import tarfile
from tempfile import TemporaryFile
from contextlib import contextmanager


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
