"""Shared utility functions."""

import json
from datetime import datetime, timezone


def format_response(status_code, body):
    """Format a standard API response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def get_timestamp():
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()
