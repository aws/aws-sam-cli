"""
Custom exceptions raised by this local library
"""


class NoApisDefined(Exception):
    """
    Raised when there are no APIs defined in the template
    """


class OverridesNotWellDefinedError(Exception):
    """
    Raised when the overrides file is invalid
    """


class NoPrivilegeException(Exception):
    """
    Process does not have the required privilege to complete the action
    """


class InvalidIntermediateImageError(Exception):
    """
    Raised when there is no valid intermediate image to build on top of
    for Image based PackageTypes.
    """
