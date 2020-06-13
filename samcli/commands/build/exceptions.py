"""Build exceptions"""

from samcli.commands.exceptions import UserException


class InvalidBuildDirException(UserException):
    """
    Value provided to --build-dir is invalid
    """


class MissingBuildMethodException(UserException):
    """
    Exception to be thrown when a layer is tried to build without BuildMethod
    """
