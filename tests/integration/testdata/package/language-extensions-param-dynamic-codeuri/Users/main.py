"""Users service handler for package tests."""


def handler(event, context):
    """Lambda handler for Users service."""
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from Users service",
            "service": "UsersService"
        }
    }
