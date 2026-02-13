"""Orders service handler for package tests."""


def handler(event, context):
    """Lambda handler for Orders service."""
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from Orders service",
            "service": "OrdersService"
        }
    }
