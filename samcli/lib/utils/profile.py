"""
Module for aws profile related helpers
"""

from typing import List

from botocore.session import Session


def list_available_profiles() -> List[str]:
    return Session().available_profiles
