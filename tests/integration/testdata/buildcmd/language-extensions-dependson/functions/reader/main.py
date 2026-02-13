"""Reader function handler."""

import os


def handler(event, context):
    table = os.environ.get("TABLE_NAME", "unknown")
    role = os.environ.get("ROLE", "unknown")
    return {
        "statusCode": 200,
        "body": {"table": table, "role": role},
    }
