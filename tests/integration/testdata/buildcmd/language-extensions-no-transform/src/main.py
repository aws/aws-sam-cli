"""Standard SAM handler (no language extensions)."""

import os


def handler(event, context):
    function_name = os.environ.get("FUNCTION_NAME", "Unknown")
    return {
        "statusCode": 200,
        "body": {"message": f"Hello from {function_name}"},
    }
