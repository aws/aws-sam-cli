"""Beta function handler for package tests."""


def handler(event, context):
    """Lambda handler for Beta function."""
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from Beta",
            "function": "BetaFunction"
        }
    }
