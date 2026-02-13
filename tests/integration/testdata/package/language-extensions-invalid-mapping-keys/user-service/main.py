"""User service function handler for package tests."""


def handler(event, context):
    """Lambda handler for user-service function."""
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from user-service",
            "service": "user-service"
        }
    }
