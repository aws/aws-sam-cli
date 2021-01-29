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


class MissingMetadataForImageFunctionException(UserException):
    """
    Exception to be thrown when a function has Image package type but no metadata is defined
    """


class InvalidPackageTypeException(UserException):
    """
    Exception to be thrown when package type is not a valid value
    """
