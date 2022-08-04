"""
The container for Testable Resources
"""
from typing import Any
from dataclasses import dataclass


@dataclass
class TestableResDef:
    LogicalResourceId: str
    PhysicalResourceId: str
    CloudEndpointOrFunctionURL: Any
    Methods: Any
