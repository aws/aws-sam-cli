"""
Custom Exceptions for 'sam validate' commands
"""

from samcli.commands.exceptions import UserException


class InvalidSamDocumentException(UserException):
    """
    Exception for Invalid Sam Documents
    """
