"""
Exceptions to be used by samconfig.py
"""


from samcli.commands.exceptions import UserException


class SamConfigVersionException(UserException):
    """Exception for the `samconfig` file being not present or in unrecognized format"""

    pass


class FileParseException(UserException):
    """Exception when a file is incorrectly parsed by a FileManager object."""

    pass


class SamConfigFileReadException(UserException):
    """Exception when a `samconfig` file is read incorrectly."""

    pass
