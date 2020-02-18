"""
Class containing error conditions that are exposed to the user.
"""

from samcli.commands.exceptions import UserException


class InvokeContextException(UserException):
    """
    Something went wrong invoking the function.
    """


class InvalidSamTemplateException(UserException):
    """
    The template provided was invalid and not able to transform into a Standard CloudFormation Template
    """


class SamTemplateNotFoundException(UserException):
    """
    The SAM Template provided could not be found
    """


class DebugContextException(UserException):
    """
    Something went wrong when creating the DebugContext
    """


class ImageBuildException(UserException):
    """
    Image failed to build
    """


class CredentialsRequired(UserException):
    """
    Credentials were not given when Required
    """


class ResourceNotFound(UserException):
    """
    The Resource requested was not found
    """


class InvalidLayerVersionArn(UserException):
    """
    The LayerVersion Arn given in the template is Invalid
    """


class UnsupportedIntrinsic(UserException):
    """
    Value from a template has an Intrinsic that is unsupported
    """


class NotAvailableInRegion(UserException):
    """
    Calling service not available (launched) in specified region
    """
