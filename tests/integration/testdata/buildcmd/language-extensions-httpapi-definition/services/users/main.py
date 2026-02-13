"""Lambda handler for users HTTP API service."""

import json
import os


def handler(event, context):
    service_name = os.environ.get("SERVICE_NAME", "Unknown")
    path = event.get("rawPath", "/")
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "service": service_name,
            "path": path,
            "method": method,
            "data": [
                {"id": "1", "name": "Alice"},
                {"id": "2", "name": "Bob"},
            ],
        }),
    }
