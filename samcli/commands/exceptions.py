"""
Class containing error conditions that are exposed to the user.
"""

import click


class ConfigException(click.ClickException):
    """ """


class UserException(click.ClickException):
    """Base class for all exceptions that need to be surfaced to the user. Typically, we will display the exception
    message to user and return the error code from CLI process

    Parameters
    ----------

    Returns
    -------

    """

    exit_code = 1

    def __init__(self, message, wrapped_from=None):
        self.wrapped_from = wrapped_from

        click.ClickException.__init__(self, message)


class CredentialsError(UserException):
    """ """


class SchemasApiException(UserException):
    """ """


class RegionError(UserException):
    """ """


class AppTemplateUpdateException(UserException):
    """ """
