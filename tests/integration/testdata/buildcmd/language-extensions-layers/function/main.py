"""Lambda function that uses all three ForEach-generated layers."""

import json


def handler(event, context):
    results = {}

    # Test common layer
    try:
        from common_utils import format_response, get_timestamp
        results["common_layer"] = "loaded"
        results["timestamp"] = get_timestamp()
    except ImportError as e:
        results["common_layer"] = f"failed: {e}"

    # Test database layer
    try:
        from db_helper import get_table, scan_table
        results["database_layer"] = "loaded"
    except ImportError as e:
        results["database_layer"] = f"failed: {e}"

    # Test auth layer
    try:
        from auth_helper import validate_token, get_user_from_token
        results["auth_layer"] = "loaded"
        valid, msg = validate_token("Bearer test-token")
        results["auth_valid"] = valid
    except ImportError as e:
        results["auth_layer"] = f"failed: {e}"

    return {
        "statusCode": 200,
        "body": json.dumps(results),
    }
