"""
Common OS utilities
"""

import sys
import os
import shutil
import tempfile

from contextlib import contextmanager


@contextmanager
def mkdir_temp(mode=0o755):
    """
    Context manager that makes a temporary directory and yields it name. Directory is deleted
    after the context exits

    Parameters
    ----------
    mode : octal
        Permissions to apply to the directory. Defaults to '755' because don't want directories world writable

    Returns
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
            shutil.rmtree(temp_dir)


def stdout():
    """
    Returns the stdout as a byte stream in a Py2/PY3 compatible manner

    Returns
    -------
    io.BytesIO
        Byte stream of Stdout
    """

    # We write all of the data to stdout with bytes, typically io.BytesIO. stdout in Python2
    # accepts bytes but Python3 does not. This is due to a type change on the attribute. To keep
    # this consistent, we leave Python2 the same and get the .buffer attribute on stdout in Python3
    byte_stdout = sys.stdout

    if sys.version_info.major > 2:
        byte_stdout = sys.stdout.buffer  # pylint: disable=no-member

    return byte_stdout


def stderr():
    """
    Returns the stderr as a byte stream in a Py2/PY3 compatible manner

    Returns
    -------
    io.BytesIO
        Byte stream of stderr
    """

    # We write all of the data to stderr with bytes, typically io.BytesIO. stderr in Python2
    # accepts bytes but Python3 does not. This is due to a type change on the attribute. To keep
    # this consistent, we leave Python2 the same and get the .buffer attribute on stderr in Python3
    byte_stderr = sys.stderr

    if sys.version_info.major > 2:
        byte_stderr = sys.stderr.buffer  # pylint: disable=no-member

    return byte_stderr
