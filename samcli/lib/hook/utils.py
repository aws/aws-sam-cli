"""
Hook-related utils
"""

from typing import Dict, Optional

HOOK_METADATA_KEY = "AWS::SAM::Hook"


def get_hook_metadata(template: Dict[str, Dict]) -> Optional[Dict]:
    """
    Returns Hook Metadata from the given template if it exists.
    If the metadata is not found, returns None.

    Parameters
    ----------
    template:
        CFN template to look through

    Returns
    ----------
    Optional[Dict]:
        Hook metadata

    """

    metadata = template.get("Metadata", {}) if template else {}
    return metadata.get(HOOK_METADATA_KEY)
