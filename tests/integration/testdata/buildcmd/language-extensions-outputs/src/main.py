"""Handler for outputs test."""

import os


def handler(event, context):
    function_name = os.environ.get("FUNCTION_NAME", "unknown")
    return {
        "statusCode": 200,
        "body": {"function": function_name},
    }
