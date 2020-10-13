"""
Provides utility functions to centralize logic for AWS SAM CLI feature flags in a single file.
"""

from os import getenv

EXTENSIONS_PREVIEW_ENV = "ENABLE_LAMBDA_EXTENSIONS_PREVIEW"


def extensions_preview_enabled():
    """
    Checks the ENABLE_LAMBDA_EXTENSIONS_PREVIEW env variable to determine if functionality for the
    extensions preview should be enabled or not.
    """
    env_value = getenv(EXTENSIONS_PREVIEW_ENV)
    if env_value == "1":
        return True
    return False
