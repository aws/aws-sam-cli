"""
Custom Exceptions for Init module
"""


class InitErrorException(Exception):
    fmt = "An unspecified error occurred"

    def __init__(self, **kwargs):
        msg = self.fmt.format(**kwargs)
        Exception.__init__(self, msg)
        self.kwargs = kwargs


class GenerateProjectFailedError(InitErrorException):
    fmt = "An error occurred while generating this project {project}: {provider_error}"


class InvalidLocationError(InitErrorException):
    fmt = "The template location specified is not valid: {template}"


class ArbitraryProjectDownloadFailed(InitErrorException):
    fmt = "{msg}"
