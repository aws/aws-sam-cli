"""
Exceptions that are used by remote invoke or remote test-events commands
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


class DuplicateEventName(UserException):
    pass


class EventTooLarge(UserException):
    pass


class InvalidSchema(UserException):
    pass


class InvalidEventOutputFile(UserException):
    pass


class ResourceNotSupportedForTestEvents(UserException):
    pass


class IllFormedEventData(UserException):
    pass
