"""
The container for stack outputs
"""
from dataclasses import dataclass


@dataclass
class StackOutputs:
    OutputKey: str
    OutputValue: str
    Description: str

    def __init__(self, OutputKey, OutputValue, Description):
        self.OutputKey = OutputKey
        self.OutputValue = OutputValue
        self.Description = Description
