# Backend function for APIs
# This file is part of the language-extensions-dynamic-definitionuri-api test

import json

def handler(event, context):
    """Lambda handler for API backend."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({"message": "Hello from API backend"})
    }
