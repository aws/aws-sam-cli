"""
Base Authorizer class definition
"""
from dataclasses import dataclass


@dataclass
class Authorizer:
    payload_version: str
    authorizer_name: str
    type: str
