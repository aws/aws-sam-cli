"""
Docker container related exceptions
"""

from samcli.commands.exceptions import UserException


class ContainerNotStartableException(Exception):
    pass


class NoFreePortsError(Exception):
    """
    Exception to raise when there are no free ports found in a specified range.
    """


class PortAlreadyInUse(Exception):
    """
    Exception to raise when the provided port is not available for use.
    """


class ContainerFailureError(UserException):
    """
    Raised when the invoke container fails execution
    """
