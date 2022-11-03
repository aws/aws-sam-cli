"""
Hook-related utils
"""

from typing import Dict, Optional, Any

HOOK_METADATA_KEY = "AWS::Sam::Hook"


def get_hook_metadata(template: Dict) -> Optional[Any]:
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

    metadata = template.get("Metadata", {})
    return metadata.get(HOOK_METADATA_KEY)
