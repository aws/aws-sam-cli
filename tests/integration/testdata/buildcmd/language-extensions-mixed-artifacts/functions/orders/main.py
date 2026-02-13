"""Lambda handler for orders service."""

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
                {"id": "ORD-001", "status": "shipped"},
                {"id": "ORD-002", "status": "pending"},
            ],
        }),
    }
