"""
Architecture tools
"""
import logging
from typing import TYPE_CHECKING

from samcli.commands.exceptions import UserException
from samcli.commands.local.lib.exceptions import UnsupportedRuntimeArchitectureError
from samcli.lib.runtimes.base import Architecture, Runtime
from samcli.lib.utils.packagetype import IMAGE

if TYPE_CHECKING:  # pragma: no cover
    from samcli.lib.providers.provider import Function

LOG = logging.getLogger(__name__)

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

    runtime_architectures = []
    try:
        runtime = Runtime.from_str(function.runtime)
        runtime_architectures.extend(runtime.value.archs_as_list_of_str())
    except ValueError:
        LOG.debug("Unrecognized runtime %s", function.runtime)

    if function.architectures and function.architectures[0] not in runtime_architectures:
        raise UnsupportedRuntimeArchitectureError(
            f"Runtime {function.runtime} is not supported on '{function.architectures[0]}' architecture"
        )


def has_runtime_multi_arch_image(runtime: str) -> bool:
    try:
        r = Runtime.from_str(runtime)
        return len(r.value.archs) > 1
    except ValueError:
        LOG.debug("Unrecognized runtime %s", runtime)
    return False


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
    try:
        Architecture(architecture)
        return
    except ValueError:
        raise InvalidArchitecture(f"Architecture '{architecture}' is invalid. Valid values are {Architecture.ARM64.value} or {Architecture.X86_64.value}")
