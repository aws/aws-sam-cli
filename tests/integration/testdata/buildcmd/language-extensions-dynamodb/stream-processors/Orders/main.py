"""Lambda handler for Orders DynamoDB stream events."""

import json
import os


def handler(event, context):
    table_name = os.environ.get("TABLE_NAME", "Unknown")
    records = event.get("Records", [])
    for record in records:
        event_name = record.get("eventName", "UNKNOWN")
        keys = record.get("dynamodb", {}).get("Keys", {})
        print(f"[{table_name}] {event_name}: {json.dumps(keys)}")
    return {
        "statusCode": 200,
        "body": json.dumps({
            "table": table_name,
            "records_processed": len(records),
        }),
    }
