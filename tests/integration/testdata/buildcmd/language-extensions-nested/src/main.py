"""
Simple Lambda handler for nested stack language extensions test.
Used by both parent and child templates.
"""

import os


def handler(event, context):
    """
    Lambda handler that returns information about the function.
    
    Returns:
        dict: Response containing function metadata
    """
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from nested stack test",
            "function_name": os.environ.get("FUNCTION_NAME", "unknown"),
            "stack_type": os.environ.get("STACK_TYPE", "unknown"),
            "environment": os.environ.get("ENVIRONMENT", "unknown"),
            "total_child_functions": os.environ.get("TOTAL_CHILD_FUNCTIONS", "N/A")
        }
    }
