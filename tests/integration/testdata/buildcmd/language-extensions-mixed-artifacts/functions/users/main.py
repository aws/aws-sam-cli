"""Lambda handler for users service."""

import json
import os


def handler(event, context):
    service_name = os.environ.get("SERVICE_NAME", "Unknown")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "service": service_name,
            "data": [
                {"id": "1", "name": "Alice"},
                {"id": "2", "name": "Bob"},
            ],
        }),
    }
