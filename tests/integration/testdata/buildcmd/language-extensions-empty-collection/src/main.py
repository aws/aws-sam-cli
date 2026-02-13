"""Handler for empty collection test (used only if collection is non-empty)."""

import os


def handler(event, context):
    function_name = os.environ.get("FUNCTION_NAME", "Unknown")
    return {
        "statusCode": 200,
        "body": {"message": f"Hello from {function_name}"},
    }
