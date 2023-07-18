"""
Architecture tools
"""
from typing import TYPE_CHECKING, Dict, List, cast

from samcli.commands.exceptions import UserException
from samcli.commands.local.lib.exceptions import UnsupportedRuntimeArchitectureError
from samcli.lib.utils.packagetype import IMAGE

if TYPE_CHECKING:  # pragma: no cover
    from samcli.lib.providers.provider import Function

X86_64 = "x86_64"
ARM64 = "arm64"

SUPPORTED_RUNTIMES: Dict[str, List[str]] = {
    "nodejs12.x": [ARM64, X86_64],
    "nodejs14.x": [ARM64, X86_64],
    "nodejs16.x": [ARM64, X86_64],
    "nodejs18.x": [ARM64, X86_64],
    "python3.7": [X86_64],
    "python3.8": [ARM64, X86_64],
    "python3.9": [ARM64, X86_64],
    "python3.10": [ARM64, X86_64],
    "python3.11": [ARM64, X86_64],
    "ruby2.7": [ARM64, X86_64],
    "ruby3.2": [ARM64, X86_64],
    "java8": [X86_64],
    "java8.al2": [ARM64, X86_64],
    "java11": [ARM64, X86_64],
    "java17": [ARM64, X86_64],
    "go1.x": [X86_64],
    "dotnet6": [ARM64, X86_64],
    "provided": [X86_64],
    "provided.al2": [ARM64, X86_64],
}


def validate_architecture_runtime(function: "Function") -> None:
    """
    Validates that a function runtime and architecture are compatible for invoking

    Parameters
    ----------
    function : samcli.commands.local.lib.provider.Function
        Lambda function

    Raises
    ------
    samcli.commands.local.lib.exceptions.UnsupportedRuntimeArchitectureError
        If the runtime and architecture are not compatible
    """
    if function.packagetype == IMAGE:
        return

    runtime_architectures = SUPPORTED_RUNTIMES.get(cast(str, function.runtime), [])

    if function.architectures and function.architectures[0] not in runtime_architectures:
        raise UnsupportedRuntimeArchitectureError(
            f"Runtime {function.runtime} is not supported on '{function.architectures[0]}' architecture"
        )


def has_runtime_multi_arch_image(runtime: str):
    return len(SUPPORTED_RUNTIMES.get(runtime, [])) > 1


class InvalidArchitecture(UserException):
    """
    Exception to raise when an invalid Architecture is provided.
    """


def validate_architecture(architecture: str) -> None:
    """
    Validates an architecture value

    Parameters
    ----------
    architecture : str
        Value

    Raises
    ------
    InvalidArchitecture
        If the architecture is unknown
    """
    if architecture not in [ARM64, X86_64]:
        raise InvalidArchitecture(f"Architecture '{architecture}' is invalid. Valid values are {ARM64} or {X86_64}")
