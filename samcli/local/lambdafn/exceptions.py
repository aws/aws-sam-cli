"""
Custom exception used by Local Lambda execution
"""


class FunctionNotFound(Exception):
    """
    Raised when the requested Lambda function is not found
    """


class ResourceNotFound(Exception):
    """
    Raised when the requested resource is not found
    """
