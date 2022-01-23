""" Exceptions raised from the cookiecutter workflow"""


class CookiecutterErrorException(Exception):
    fmt = "An unspecified error occurred"

    def __init__(self, **kwargs):  # type: ignore
        msg: str = self.fmt.format(**kwargs)
        Exception.__init__(self, msg)
        self.kwargs = kwargs


class GenerateProjectFailedError(CookiecutterErrorException):
    fmt = "An error occurred while generating project from the template {template}: {provider_error}"


class InvalidLocationError(CookiecutterErrorException):
    fmt = "The template location specified is not valid: {template}"


class PreprocessingError(CookiecutterErrorException):
    fmt = "An error occurred while preprocessing {template}: {provider_error}"


class PostprocessingError(CookiecutterErrorException):
    fmt = "An error occurred while postprocessing {template}: {provider_error}"
