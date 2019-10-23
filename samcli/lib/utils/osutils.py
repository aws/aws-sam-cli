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
