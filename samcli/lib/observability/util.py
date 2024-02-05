"""
Utility classes and methods for observability commands and functionality
"""

from enum import Enum


class OutputOption(Enum):  # pragma: no cover
    """
    Used to configure how output will be presented with observability commands
    """

    text = "text"  # default
    json = "json"
