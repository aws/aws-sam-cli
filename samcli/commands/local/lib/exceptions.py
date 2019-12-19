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
