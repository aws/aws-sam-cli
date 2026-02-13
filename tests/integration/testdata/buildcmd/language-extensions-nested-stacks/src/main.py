"""Parent stack handler."""

import os


def handler(event, context):
    stack_type = os.environ.get("STACK_TYPE", "unknown")
    return {
        "statusCode": 200,
        "body": {"stack_type": stack_type},
    }
