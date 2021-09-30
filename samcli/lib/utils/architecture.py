"""
Architecture tools
"""

from samcli.commands.exceptions import UserException

X86_64 = "x86_64"
ARM64 = "arm64"


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
