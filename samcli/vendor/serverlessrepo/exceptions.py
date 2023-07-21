"""Collection of public exceptions raised by this library."""


class ServerlessRepoError(Exception):
    """Base exception raised by serverlessrepo library."""

    MESSAGE = ""

    def __init__(self, **kwargs):
        """Init the exception object."""
        Exception.__init__(self, self.MESSAGE.format(**kwargs))


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


class ServerlessRepoClientError(ServerlessRepoError):
    """Wrapper for botocore ClientError."""

    MESSAGE = "{message}"
