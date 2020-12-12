"""
Class containing error conditions that are exposed to the user.
"""

import click


class ConfigException(click.ClickException):
    """
    Exception class when configuration file fails checks.
    """


class UserException(click.ClickException):
    """
    Base class for all exceptions that need to be surfaced to the user. Typically, we will display the exception
    message to user and return the error code from CLI process
    """

    exit_code = 1

    def __init__(self, message, wrapped_from=None):
        self.wrapped_from = wrapped_from

        click.ClickException.__init__(self, message)


class CredentialsError(UserException):
    """
    Exception class when credentials that have been passed are invalid.
    """


class SchemasApiException(UserException):
    """
    Exception class to wrap all Schemas APIs exceptions.
    """


class RegionError(UserException):
    """
    Exception class when no valid region is passed to a client.
    """


class AppTemplateUpdateException(UserException):
    """
    Exception class when updates to app templates for init enters an unstable state.
    """


class LambdaImagesTemplateException(UserException):
    """
    Exception class when multiple Lambda Image app templates are found for any runtime
    """


class ContainersInitializationException(UserException):
    """
    Exception class when SAM is not able to initialize any of the lambda functions containers
    """
