"""Lambda handler for OrderEvents SNS topic."""

import json
import os


def handler(event, context):
    topic_name = os.environ.get("TOPIC_NAME", "Unknown")
    records = event.get("Records", [])
    for record in records:
        message = record.get("Sns", {}).get("Message", "")
        print(f"[{topic_name}] Received: {message}")
    return {
        "statusCode": 200,
        "body": json.dumps({
            "topic": topic_name,
            "records_processed": len(records),
        }),
    }
