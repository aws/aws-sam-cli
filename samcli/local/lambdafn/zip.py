"""
Helper methods to unzip an archive preserving the file permissions. Python's zipfile module does not yet support
this feature natively (https://bugs.python.org/issue15795).
"""

import os
import zipfile
import logging

import requests

from samcli.lib.utils.progressbar import progressbar

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


LOG = logging.getLogger(__name__)


S_IFLNK = 0xA


def issymlink(file_info):
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

    return (file_info.external_attr >> 28) == S_IFLNK


def extract(file_info, output_dir, zip_ref):
    """
    ----------------------------------------------------------------------------
    Extract: read the link path string, and make a new symlink.

    'zipinfo' is the link file's ZipInfo object stored in zipfile.
    'pathto'  is the extract's destination folder (relative or absolute)
    'zipfile' is the ZipFile object, which reads and parses the zip file.

    On Windows, this requires admin permission and an NTFS destination drive.
    On Unix, this generally works with any writable drive and normal permission.

    Uses target_is_directory on Windows if flagged as dir in zip bits: it's not
    impossible that the extract may reach a dir link before its dir target.

    Adjusts link path text for host's separators to make links portable across
    Windows and Unix, unless 'nofixlinks' (which is command arg -nofixlinks).
    This is switchable because it assumes the target is a drive to be used
    on this platform - more likely here than for mergeall external drives.

    Caveat: some of this code mimics that in zipfile.ZipFile._extract_member(),
    but that library does not expose it for reuse here.  Some of this is also
    superfluous if we only unzip what we zip (e.g., Windows drive names won't
    be present and upper dirs will have been created), but that's not ensured.

    In ziptools, pathto already has a '\\?\' long-path prefix on Windows (only);
    this ensures that the file calls here work regardless of joined-path length.

    TBD: should we also call os.chmod() with the zipinfo's permission bits?
    TBD: does the UTF8 decoding of the unzip pathname here suffice everywhere?
    ----------------------------------------------------------------------------
    """

    if not issymlink(file_info):
        return zip_ref.extract(file_info, output_dir)

    zippath = file_info.filename  # pathname in the zip
    linkpath = zipfile.read(zippath)  # original link path str
    linkpath = linkpath.decode('utf8')  # must be same types

    # undo zip-mandated '/' separators on Windows
    zippath = zippath.replace('/', os.sep)  # no-op if unix or simple

    # drop Win drive + unc, leading slashes, '.' and '..'
    zippath = os.path.splitdrive(zippath)[1]
    zippath = zippath.lstrip(os.sep)  # if other programs' zip
    allparts = zippath.split(os.sep)
    okparts = [p for p in allparts if p not in ('.', '..')]
    zippath = os.sep.join(okparts)

    # where to store link now
    destpath = os.path.join(output_dir, zippath)  # hosting machine path
    destpath = os.path.normpath(destpath)  # perhaps moot, but...

    # make leading dirs if needed
    upperdirs = os.path.dirname(destpath)
    if not os.path.exists(upperdirs):  # don't fail if exists
        os.makedirs(upperdirs)  # exists_ok in py 3.2+

    # test+remove link, not target
    if os.path.lexists(destpath):  # else symlink() fails
        os.remove(destpath)

    # make the link in dest (mtime: caller)
    os.symlink(linkpath, destpath)  # store new link in dest
    return destpath  # mtime is set in caller


def unzip(zip_file_path, output_dir, permission=None):
    """
    Unzip the given file into the given directory while preserving file permissions in the process.

    Parameters
    ----------
    zip_file_path : str
        Path to the zip file

    output_dir : str
        Path to the directory where the it should be unzipped to

    permission : octal int
        Permission to set
    """

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:

        # For each item in the zip file, extract the file and set permissions if available
        for file_info in zip_ref.infolist():
            extracted_path = extract(file_info, output_dir, zip_ref)
            _set_permissions(file_info, extracted_path)

            _override_permissions(extracted_path, permission)

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
        get_request = requests.get(uri, stream=True)

        with open(layer_zip_path, 'wb') as local_layer_file:
            file_length = int(get_request.headers['Content-length'])

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
