"""
Exceptions that is used by remote invoke command
"""
from samcli.commands.exceptions import UserException


class InvalidRemoteInvokeParameters(UserException):
    pass


class NoResourceFoundForRemoteInvoke(UserException):
    pass


class AmbiguousResourceForRemoteInvoke(UserException):
    pass


class UnsupportedServiceForRemoteInvoke(UserException):
    pass


class ResourceNotSupportedForRemoteInvoke(UserException):
    pass


class InvalidStackNameProvidedForRemoteInvoke(UserException):
    pass
