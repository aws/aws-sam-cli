"""Common utilities shared across Lambda functions."""


def format_response(status_code, body):
    """Format a standard API response."""
    import json
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def get_timestamp():
    """Return current UTC timestamp as ISO string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
