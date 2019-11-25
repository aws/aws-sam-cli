"""
Helper functions for temporary files
"""
import os
import contextlib
import tempfile


def remove(path):
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


@contextlib.contextmanager
def tempfile_platform_independent():
    # NOTE(TheSriram): Setting delete=False is specific to windows.
    # https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    _tempfile = tempfile.NamedTemporaryFile(delete=False)
    try:
        yield _tempfile
    finally:
        _tempfile.close()
        remove(_tempfile.name)
