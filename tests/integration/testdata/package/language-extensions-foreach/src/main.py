"""
Lambda function handler for language extensions package test.
"""

import os


def handler(event, context):
    """
    Simple Lambda handler that returns the function name from environment variable.
    """
    function_name = os.environ.get("FUNCTION_NAME", "Unknown")
    return {
        "statusCode": 200,
        "body": f"Hello from {function_name}Function!"
    }
