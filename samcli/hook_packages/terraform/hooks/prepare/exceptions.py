"""
Module containing prepare hook-related exceptions
"""


class InvalidResourceLinkingException(Exception):
    fmt = "An error occurred when attempting to link two resources: {message}"

    def __init__(self, message):
        msg = self.fmt.format(message=message)
        Exception.__init__(self, msg)
