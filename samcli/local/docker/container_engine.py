"""
Container engine type definitions and enums
"""

from enum import Enum


class ContainerEngine(Enum):
    FINCH = "finch"
    DOCKER = "docker"
