"""
Custom exception used by Local Lambda execution
"""


class FunctionNotFound(Exception):
    """
    Raised when the requested Lambda function is not found
    """
    pass
