"""Lambda handler shared by all ForEach-generated functions."""

import os


def handler(event, context):
    function_name = os.environ.get("FUNCTION_NAME", "Unknown")
    return {
        "statusCode": 200,
        "body": {
            "message": f"Hello from {function_name}",
            "function": f"{function_name}Function",
        },
    }
