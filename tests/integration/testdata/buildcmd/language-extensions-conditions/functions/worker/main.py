"""Worker handler for conditions test."""

import os


def handler(event, context):
    name = os.environ.get("FUNCTION_NAME", "unknown")
    env = os.environ.get("ENVIRONMENT", "unknown")
    return {
        "statusCode": 200,
        "body": {"function": name, "environment": env},
    }
