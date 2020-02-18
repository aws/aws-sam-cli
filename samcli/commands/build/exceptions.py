"""Build exceptions"""

from samcli.commands.exceptions import UserException


class InvalidBuildDirException(UserException):
    """
    Value provided to --build-dir is invalid
    """
