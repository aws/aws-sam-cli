"""
Exceptions to be used by samconfig.py
"""


class SamConfigVersionException(Exception):
    """Exception for the `samconfig` file being not present or in unrecognized format"""


class FileParseException(Exception):
    """Exception when a file is incorrectly parsed by a FileManager object."""


class SamConfigFileReadException(Exception):
    """Exception when a `samconfig` file is read incorrectly."""
