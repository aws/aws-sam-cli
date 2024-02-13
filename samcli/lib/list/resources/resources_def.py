"""
The container for Resources
"""

from dataclasses import dataclass


@dataclass
class ResourcesDef:
    LogicalResourceId: str
    PhysicalResourceId: str
