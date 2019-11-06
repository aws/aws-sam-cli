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


class CredentialsError(UserException):
    """
    Exception class when credentials that have been passed are invalid.
    """
