"""Dev API handler."""

import os


def handler(event, context):
    env = os.environ.get("ENV", "unknown")
    service = os.environ.get("SERVICE", "unknown")
    return {
        "statusCode": 200,
        "body": {"message": f"Hello from {env}/{service}", "env": env, "service": service},
    }
