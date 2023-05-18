"""
Exceptions used by remote invoke executors
"""


class InvalidResourceBotoParameterException(Exception):
    """Exception is raised when parameters passed to boto APIs are invalid"""

    pass


class InvalideBotoResponseException(Exception):
    """Exception is raised when the boto APIs return an invalid response"""

    pass
