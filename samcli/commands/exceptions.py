"""
Class containing error conditions that are exposed to the user.
"""
import traceback
from typing import IO, Optional
from urllib.parse import quote

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


class UnhandledException(click.ClickException):
    """
    Exception class to re-wrap any exception that is not a UserException.
    Typically this means there is a bug in SAM CLI.
    """

    GH_ISSUE_SEARCH_URL = "https://github.com/aws/aws-sam-cli/issues?q=is%3Aissue+is%3Aopen+{title}"
    GH_BUG_REPORT_URL = "https://github.com/aws/aws-sam-cli/issues/new?template=Bug_report.md&title={title}"
    # NOTE (hawflau): actual exitcode is 1 to not break existing behavior. Only report 255 to telemetry
    exit_code = 1

    def __init__(self, command: str, exception: Exception) -> None:
        self._command = command
        self._exception = exception
        self.__traceback__ = self._exception.__traceback__

        click.ClickException.__init__(self, type(exception).__name__)

    def show(self, file: Optional[IO] = None) -> None:
        """Overriding show to customize printing stack trace and message"""
        if file is None:
            file = click._compat.get_text_stderr()  # pylint: disable=protected-access

        tb = "".join(traceback.format_tb(self.__traceback__))
        click.echo(f"\nError: {self._exception}", file=file, err=True)
        click.echo(f"Traceback:\n{tb}", file=file, err=True)

        encoded_title = quote(f"Bug: {self._command} - {type(self._exception).__name__}")
        lookup_url = self.GH_ISSUE_SEARCH_URL.format(title=encoded_title)
        create_issue_url = self.GH_BUG_REPORT_URL.format(title=encoded_title)
        msg = (
            f'An unexpected error was encountered while executing "{self._command}".\n'
            "Search for an existing issue:\n"
            f"{lookup_url}\n"
            "Or create a bug report:\n"
            f"{create_issue_url}"
        )
        click.secho(msg, file=file, err=True, fg="yellow")


class AWSServiceClientError(UserException):
    """
    Exception class when there are errors calling any AWS services via Boto.
    """


class SDKError(UserException):
    """
    Exception class when there are generic Boto Errors.
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


class PipelineTemplateCloneException(UserException):
    """
    Exception class when unable to download pipeline templates from a Git repository during `sam pipeline init`
    """


class AppPipelineTemplateManifestException(UserException):
    """
    Exception class when SAM is not able to parse the "manifest.yaml" file located in the SAM pipeline templates
    Git repo: "github.com/aws/aws-sam-cli-pipeline-init-templates.git
    """


class AppPipelineTemplateMetadataException(UserException):
    """
    Exception class when SAM is not able to parse the "metadata.json" file located in the SAM pipeline templates
    """


class InvalidInitOptionException(UserException):
    """
    Exception class when user provides wrong options
    """


class InvalidImageException(UserException):
    """
    Value provided to --build-image or --invoke-image is invalid URI
    """


class InvalidStackNameException(UserException):
    """
    Value provided to --stack-name is invalid
    """


class LinterRuleMatchedException(UserException):
    """
    The linter matched a rule meaning that the template linting failed
    """
