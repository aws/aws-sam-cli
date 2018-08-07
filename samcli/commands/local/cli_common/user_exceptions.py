"""
Class containing error conditions that are exposed to the user.
"""

from samcli.commands.exceptions import UserException


class InvokeContextException(UserException):
    """
    Something went wrong invoking the function.
    """
    pass


class InvalidSamTemplateException(UserException):
    """
    The template provided was invalid and not able to transform into a Standard CloudFormation Template
    """
    pass


class SamTemplateNotFoundException(UserException):
    """
    The SAM Template provided could not be found
    """
    pass


class DebugContextException(UserException):
    """
    Something went wrong when creating the DebugContext
    """
    pass
