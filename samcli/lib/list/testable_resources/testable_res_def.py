"""
The container for Testable Resources
"""
from typing import Any
from dataclasses import dataclass


@dataclass
class TestableResDef:
    """
    Dataclass for containing entries of testable resources data
    """

    LogicalResourceId: str
    PhysicalResourceId: str
    CloudEndpointOrFunctionURL: Any
    Methods: Any
