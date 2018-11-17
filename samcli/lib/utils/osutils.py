"""
Common OS utilities
"""

import os
import shutil
import tempfile

from contextlib import contextmanager


@contextmanager
def mkdir_temp(mode=0o755):

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()

        if os.name == 'posix':
            os.chmod(temp_dir, mode)

        yield temp_dir

    finally:
        if temp_dir:
            shutil.rmtree(temp_dir)

