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


class ReservedEnvironmentVariableException(UserException):
    """
    Exception class when the user attempts to override a reserved environment variable during `sam test-runner run`
    """


class InvalidEnvironmentVariableException(UserException):
    """
    Exception class when the user attempts to specify invalid environment variable names or values in the
    ARN map YAML file passed to `sam test-runner run`. For example, a key that is not a valid identifier,
    a value that is None, or not a string, int, or float.
    """


class NoResourcesMatchGivenTagException(UserException):
    """
    Exception class when the user supplies tags that do not match any resources to `sam test-runner init`
    """


class FailedArnParseException(UserException):
    """
    Exception class when `sam test-runner init` fails to extract a resource name/id from an ARN.
    """


class InvalidTestRunnerTemplateException(UserException):
    """
    Exception raised when the customer passes a Test Runner CFN template to `sam test-runner run`
    that has key resources duplicated or missing.
    """


class MissingTestRunnerTemplateException(UserException):
    """
    Exception raised when the customer attempts to run a testsuite with a Test Runner stack name that does not exist,
    and does not provide a template to create it during `sam test-runner run`
    """
