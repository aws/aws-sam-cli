"""
Build Related Exceptions.
"""


class UnsupportedBuilderLibraryVersionError(Exception):
    def __init__(self, container_name: str, error_msg: str) -> None:
        msg = (
            "You are running an outdated version of Docker container '{container_name}' that is not compatible with"
            "this version of SAM CLI. Please upgrade to continue to continue with build. Reason: '{error_msg}'"
        )
        Exception.__init__(self, msg.format(container_name=container_name, error_msg=error_msg))


class ContainerBuildNotSupported(Exception):
    pass


class BuildError(Exception):
    def __init__(self, wrapped_from: str, msg: str) -> None:
        self.wrapped_from = wrapped_from
        Exception.__init__(self, msg)


class BuildInsideContainerError(Exception):
    pass


class DockerConnectionError(BuildError):
    def __init__(self, msg: str) -> None:
        BuildError.__init__(self, "DockerConnectionError", msg)


class DockerfileOutSideOfContext(BuildError):
    def __init__(self, msg: str) -> None:
        BuildError.__init__(self, "DockerfileOutSideOfContext", msg)


class DockerBuildFailed(BuildError):
    def __init__(self, msg: str) -> None:
        BuildError.__init__(self, "DockerBuildFailed", msg)


class InvalidBuildGraphException(Exception):
    def __init__(self, msg: str) -> None:
        Exception.__init__(self, msg)
