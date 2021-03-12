""" Exceptions raised from the cookiecutter workflow"""


class CookiecutterErrorException(Exception):
    fmt = "An unspecified error occurred"

    def __init__(self, **kwargs):
        msg = self.fmt.format(**kwargs)
        Exception.__init__(self, msg)
        self.kwargs = kwargs


class GenerateProjectFailedError(CookiecutterErrorException):
    fmt = "An error occurred while generating this project {project}: {provider_error}"


class InvalidLocationError(CookiecutterErrorException):
    fmt = "The template location specified is not valid: {template}"
