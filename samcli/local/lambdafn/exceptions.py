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


class DurableExecutionNotFound(Exception):
    """
    Raised when the requested durable execution is not found
    """


class UnsupportedInvocationType(Exception):
    """
    Raised when an event invocation type is used for non-durable invocations
    """
