"""Products endpoint handler."""

import json
import os


def handler(event, context):
    endpoint = os.environ.get("ENDPOINT_NAME", "unknown")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": f"Hello from {endpoint}", "endpoint": endpoint}),
    }
