"""
The container for stack outputs
"""

from dataclasses import dataclass


@dataclass
class StackOutputs:
    OutputKey: str
    OutputValue: str
    Description: str
