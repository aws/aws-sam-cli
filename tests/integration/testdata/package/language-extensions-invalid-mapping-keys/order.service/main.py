"""Order service function handler for package tests."""


def handler(event, context):
    """Lambda handler for order.service function."""
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from order.service",
            "service": "order.service"
        }
    }
