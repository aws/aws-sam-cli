"""Collection of public exceptions raised by this library."""


class ServerlessRepoError(Exception):
    """Base exception raised by serverlessrepo library."""

    MESSAGE = ""

    def __init__(self, message=None, **kwargs):
        """Init the exception object."""
        message = self.MESSAGE.format(**kwargs) if message is None else message
        Exception.__init__(self, message)


class InvalidApplicationMetadataError(ServerlessRepoError):
    """Raised when invalid application metadata is provided."""

    MESSAGE = "Invalid application metadata: '{error_message}'"


class ApplicationMetadataNotFoundError(ServerlessRepoError):
    """Raised when application metadata is not found."""

    MESSAGE = "Application metadata not found in the SAM template: '{error_message}'"


class S3PermissionsRequired(ServerlessRepoError):
    """Raised when S3 bucket access is denied."""

    MESSAGE = (
        "The AWS Serverless Application Repository does not have read access to bucket '{bucket}', "
        "key '{key}'. Please update your Amazon S3 bucket policy to grant the service read "
        "permissions to the application artifacts you have uploaded to your S3 bucket. See "
        "https://docs.aws.amazon.com/serverlessrepo/latest/devguide/serverless-app-publishing-applications.html"
        " for more details."
    )


class InvalidS3UriError(ServerlessRepoError):
    """Raised when the template contains invalid S3 URIs."""

    MESSAGE = "{message}"


class MissingSemanticVersionError(ServerlessRepoError):
    """Raised when a required semantic version is not provided"""

    # If --fail-on-same-version is set, then a Semantic Version is required


class DuplicateSemanticVersionError(ServerlessRepoError):
    """Raised when a publish is attempted with a Semantic Version that already exists"""

    # If --fail-on-same-version is set, then publish fails on duplicate semantic versions


class ServerlessRepoClientError(ServerlessRepoError):
    """Wrapper for botocore ClientError."""

    MESSAGE = "{message}"
