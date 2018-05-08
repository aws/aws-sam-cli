"""
Class containing error conditions that are exposed to the user.
"""

import click


class UserException(click.ClickException):
    """
    Base class for all exceptions that need to be surfaced to the user. Typically, we will display the exception
    message to user and return the error code from CLI process
    """

    exit_code = 1


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
