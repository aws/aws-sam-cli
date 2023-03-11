"""
Exceptions used by API Gateway service
"""
from samcli.commands.exceptions import UserException


class LambdaResponseParseException(Exception):
    """
    An exception raised when we fail to parse the response for Lambda
    """


class PayloadFormatVersionValidateException(Exception):
    """
    An exception raised when validation of payload format version fails
    """


class MultipleAuthorizerException(UserException):
    """
    An exception raised when user lists more than one Authorizer
    """


class IncorrectOasWithDefaultAuthorizerException(UserException):
    """
    An exception raised when the user provides root level Authorizers using the wrong OpenAPI Specification versions
    """


class InvalidOasVersion(UserException):
    """
    An exception raised when the user provides an invalid OpenAPI Specificaion version
    """


class InvalidSecurityDefinition(UserException):
    """
    An exception raised when the user provides an invalid security definition
    """


class InvalidLambdaAuthorizerResponse(UserException):
    """
    An exception raised when a Lambda authorizer returns an invalid response format
    """


class AuthorizerUnauthorizedRequest(UserException):
    """
    An exception raised when the request is not authorized by the authorizer
    """
