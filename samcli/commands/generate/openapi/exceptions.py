"""
Exceptions for generate openapi command
"""

from samcli.commands.exceptions import UserException


class GenerateOpenApiException(UserException):
    """Base exception for OpenAPI generation"""


class ApiResourceNotFoundException(GenerateOpenApiException):
    """Raised when specified API resource not found"""

    fmt = "API resource '{api_id}' not found in template. {message}"

    def __init__(self, api_id, message=""):
        self.api_id = api_id
        self.message = message
        msg = self.fmt.format(api_id=api_id, message=message)
        super().__init__(message=msg)


class InvalidApiResourceException(GenerateOpenApiException):
    """Raised when API resource is invalid"""

    fmt = "API resource '{api_id}' is not valid. {message}"

    def __init__(self, api_id, message=""):
        self.api_id = api_id
        self.message = message
        msg = self.fmt.format(api_id=api_id, message=message)
        super().__init__(message=msg)


class OpenApiExtractionException(GenerateOpenApiException):
    """Raised when OpenAPI extraction fails"""

    fmt = "Failed to extract OpenAPI definition: {message}"

    def __init__(self, message=""):
        self.message = message
        msg = self.fmt.format(message=message)
        super().__init__(message=msg)


class TemplateTransformationException(GenerateOpenApiException):
    """Raised when SAM transformation fails"""

    fmt = "Failed to transform SAM template: {message}"

    def __init__(self, message=""):
        self.message = message
        msg = self.fmt.format(message=message)
        super().__init__(message=msg)


class NoApiResourcesFoundException(GenerateOpenApiException):
    """Raised when no API resources found in template"""

    fmt = "No API resources found in template. {message}"

    def __init__(
        self, message="Please ensure your template contains AWS::Serverless::Api or AWS::Serverless::HttpApi resources."
    ):
        self.message = message
        msg = self.fmt.format(message=message)
        super().__init__(message=msg)


class MultipleApiResourcesException(GenerateOpenApiException):
    """Raised when multiple API resources found and no logical ID specified"""

    fmt = "Multiple API resources found: {api_ids}. Please specify --api-logical-id."

    def __init__(self, api_ids):
        self.api_ids = api_ids
        msg = self.fmt.format(api_ids=", ".join(api_ids))
        super().__init__(message=msg)
