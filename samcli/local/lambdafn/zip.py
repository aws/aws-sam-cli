"""
Helper methods to unzip an archive preserving the file permissions. Python's zipfile module does not yet support
this feature natively (https://bugs.python.org/issue15795).
"""

import os
import zipfile
import logging

LOG = logging.getLogger(__name__)


def unzip(zip_file_path, output_dir):
    """
    Unzip the given file into the given directory while preserving file permissions in the process.

    Parameters
    ----------
    zip_file_path : str
        Path to the zip file

    output_dir : str
        Path to the directory where the it should be unzipped to
    """

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:

        # For each item in the zip file, extract the file and set permissions if available
        for file_info in zip_ref.infolist():
            name = file_info.filename
            extracted_path = os.path.join(output_dir, name)

            zip_ref.extract(name, output_dir)
            _set_permissions(file_info, extracted_path)


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
