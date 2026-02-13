# Test function that uses the layers
# This file is part of the language-extensions-dynamic-contenturi test

def handler(event, context):
    """Lambda handler that uses the Common and Utils layers."""
    return {
        "statusCode": 200,
        "body": "Hello from test function"
    }
