"""
Utilities for local files handling.
"""

import os
import tempfile
import uuid
from contextlib import contextmanager
from typing import Optional

from samcli.lib.utils.hash import file_checksum, str_checksum


@contextmanager
def mktempfile():
    directory = tempfile.gettempdir()
    filename = os.path.join(directory, uuid.uuid4().hex)

    try:
        with open(filename, "w+") as handle:
            yield handle
    finally:
        if os.path.exists(filename):
            os.remove(filename)


def get_uploaded_s3_object_name(
    precomputed_md5: Optional[str] = None,
    file_content: Optional[str] = None,
    file_path: Optional[str] = None,
    extension: Optional[str] = None,
) -> str:
    """
    Generate the file name that will be used while creating the S3 Object based on the file hash value.
    This method expect either the precomuted hash value of the file, or the file content, or the file path

    Parameters
    ----------
    precomputed_md5: str
        the precomputed hash value of the file.
    file_content : str
        The file content to be uploaded to S3.
    file_path : str
        The file path to be uploaded to S3
    extension : str
        The file extension in S3
    Returns
    -------
    str
        The generated S3 Object name
    """
    if precomputed_md5:
        filemd5 = precomputed_md5
    elif file_content:
        filemd5 = str_checksum(file_content)
    elif file_path:
        filemd5 = file_checksum(file_path)
    else:
        raise Exception("Either File Content, File Path, or Precomputed Hash should has a value")

    if extension:
        filemd5 = filemd5 + "." + extension

    return filemd5
