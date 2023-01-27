"""
The container for Endpoints
"""
from typing import Any
from dataclasses import dataclass


@dataclass
class EndpointsDef:
    """
    Dataclass for containing entries of endpoints data
    """

    LogicalResourceId: str
    PhysicalResourceId: str
    CloudEndpoint: Any
    Methods: Any
