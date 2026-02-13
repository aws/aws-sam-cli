"""Lambda handler for v3 API."""

import json
import os


def handler(event, context):
    api_version = os.environ.get("API_VERSION", "Unknown")
    path = event.get("path", "/")
    method = event.get("httpMethod", "GET")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "message": f"Hello from {api_version} API",
            "api_version": api_version,
            "path": path,
            "method": method,
        }),
    }
