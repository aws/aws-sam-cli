"""
The container for Endpoints
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class EndpointsDef:
    """
    Dataclass for containing entries of endpoints data
    """

    LogicalResourceId: str
    PhysicalResourceId: str
    CloudEndpoint: Any
    Methods: Any
