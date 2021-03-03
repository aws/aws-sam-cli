"""
Helper methods to unzip an archive preserving the file permissions. Python's zipfile module does not yet support
this feature natively (https://bugs.python.org/issue15795).
"""

import os
import logging
import zipfile
from pathlib import Path

import requests

from samcli.lib.utils.progressbar import progressbar


LOG = logging.getLogger(__name__)

S_IFLNK = 0xA


def _is_symlink(file_info):
    """
    Check the upper 4 bits of the external attribute for a symlink.
    See: https://unix.stackexchange.com/questions/14705/the-zip-formats-external-file-attribute

    Parameters
    ----------
    file_info : zipfile.ZipInfo
        The ZipInfo for a ZipFile

    Returns
    -------
    bool
        A response regarding whether the ZipInfo defines a symlink or not.
    """

    return (file_info.external_attr >> 28) == 0xA


def _extract(file_info, output_dir, zip_ref):
    """
    Unzip the given file into the given directory while preserving file permissions in the process.

    Parameters
    ----------
    file_info : zipfile.ZipInfo
        The ZipInfo for a ZipFile
    output_dir : str
        Path to the directory where the it should be unzipped to
    zip_ref : zipfile.ZipFile
        The ZipFile we are working with.

    Returns
    -------
    string
        Returns the target path the Zip Entry was extracted to.
    """

    # Handle any regular file/directory entries
    if not _is_symlink(file_info):
        return zip_ref.extract(file_info, output_dir)

    source = zip_ref.read(file_info.filename).decode("utf8")
    link_name = os.path.normpath(os.path.join(output_dir, file_info.filename))

    # make leading dirs if needed
    leading_dirs = os.path.dirname(link_name)
    if not os.path.exists(leading_dirs):
        os.makedirs(leading_dirs)

    # If the link already exists, delete it or symlink() fails
    if os.path.lexists(link_name):
        os.remove(link_name)

    # Create a symbolic link pointing to source named link_name.
    os.symlink(source, link_name)

    return link_name


def unzip(zip_file_path, output_dir, permission=None):
    """
    Unzip the given file into the given directory while preserving file permissions in the process.

    Parameters
    ----------
    zip_file_path : str
        Path to the zip file
    output_dir : str
        Path to the directory where the it should be unzipped to
    permission : int
        Permission to set in an octal int form
    """

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:

        # For each item in the zip file, extract the file and set permissions if available
        for file_info in zip_ref.infolist():
            extracted_path = _extract(file_info, output_dir, zip_ref)

            # If the extracted_path is a symlink, do not set the permissions. If the target of the symlink does not
            # exist, then os.chmod will fail with FileNotFoundError
            if not os.path.islink(extracted_path):
                _set_permissions(file_info, extracted_path)
                _override_permissions(extracted_path, permission)

    if not os.path.islink(extracted_path):
        _override_permissions(output_dir, permission)


def _override_permissions(path, permission):
    """
    Forcefully override the permissions on the path

    Parameters
    ----------
    path str
        Path where the file or directory
    permission octal int
        Permission to set

    """
    if permission:
        os.chmod(path, permission)


def _set_permissions(zip_file_info, extracted_path):
    """
    Sets permissions on the extracted file by reading the ``external_attr`` property of given file info.

    Parameters
    ----------
    zip_file_info : zipfile.ZipInfo
        Object containing information about a file within a zip archive

    extracted_path : str
        Path where the file has been extracted to
    """

    # Permission information is stored in first two bytes.
    permission = zip_file_info.external_attr >> 16
    if not permission:
        # Zips created on certain Windows machines, however, might not have any permission information on them.
        # Skip setting a permission on these files.
        LOG.debug("File %s in zipfile does not have permission information", zip_file_info.filename)
        return

    os.chmod(extracted_path, permission)


def unzip_from_uri(uri, layer_zip_path, unzip_output_dir, progressbar_label):
    """
    Download the LayerVersion Zip to the Layer Pkg Cache

    Parameters
    ----------
    uri str
        Uri to download from
    layer_zip_path str
        Path to where the content from the uri should be downloaded to
    unzip_output_dir str
        Path to unzip the zip to
    progressbar_label str
        Label to use in the Progressbar
    """
    try:
        get_request = requests.get(uri, stream=True, verify=os.environ.get("AWS_CA_BUNDLE", True))

        with open(layer_zip_path, "wb") as local_layer_file:
            file_length = int(get_request.headers["Content-length"])

            with progressbar(file_length, progressbar_label) as p_bar:
                # Set the chunk size to None. Since we are streaming the request, None will allow the data to be
                # read as it arrives in whatever size the chunks are received.
                for data in get_request.iter_content(chunk_size=None):
                    local_layer_file.write(data)
                    p_bar.update(len(data))

        # Forcefully set the permissions to 700 on files and directories. This is to ensure the owner
        # of the files is the only one that can read, write, or execute the files.
        unzip(layer_zip_path, unzip_output_dir, permission=0o700)

    finally:
        # Remove the downloaded zip file
        path_to_layer = Path(layer_zip_path)
        if path_to_layer.exists():
            path_to_layer.unlink()
