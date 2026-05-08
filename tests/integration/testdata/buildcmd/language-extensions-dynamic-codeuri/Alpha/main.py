"""Alpha function handler."""


def handler(event, context):
    """Lambda handler for Alpha function."""
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from Alpha",
            "function": "AlphaFunction"
        }
    }
