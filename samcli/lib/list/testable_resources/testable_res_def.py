"""
The container for Testable Resources
"""
from typing import Any
from dataclasses import dataclass


@dataclass
class TestableResDef:
    LogicalResourceId: str
    PhysicalResourceId: str
    CloudEndpointOrFURL: Any
    Methods: Any
