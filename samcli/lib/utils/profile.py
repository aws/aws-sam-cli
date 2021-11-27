"""
Module for aws profile related helpers
"""
from typing import List, cast

from botocore.session import Session


def list_available_profiles() -> List[str]:
    return cast(List[str], Session().available_profiles)
