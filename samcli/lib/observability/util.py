"""
Utility classes and methods for observability commands and functionality
"""

import json
from enum import Enum


class OutputOption(Enum):  # pragma: no cover
    """
    Used to configure how output will be presented with observability commands
    """

    text = "text"  # default
    json = "json"


def failure_result_json(ex: Exception) -> str:
    """Serialize an exception into the shared terminal failure JSON document.

    Single source of truth for the {status: "failure"} shape so build and deploy report failures
    identically. error.type prefers the exception's wrapped_from over its class name; resources come
    from the exception's resource_names when present (null otherwise).
    """
    return json.dumps(
        {
            "type": "result",
            "status": "failure",
            "error": {
                "type": getattr(ex, "wrapped_from", None) or type(ex).__name__,
                "message": str(ex),
                "resources": getattr(ex, "resource_names", None),
            },
        }
    )
