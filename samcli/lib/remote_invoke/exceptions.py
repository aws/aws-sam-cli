"""
Exceptions used by remote invoke executors
"""


class InvalidResourceBotoParameterException(Exception):
    """Exception is raised when parameters passed to boto APIs are invalid"""


class InvalideBotoResponseException(Exception):
    """Exception is raised when the boto APIs return an invalid response"""


class ErrorBotoApiCallException(Exception):
    """Exception is raised when calling boto APIs returns an error while execution"""
