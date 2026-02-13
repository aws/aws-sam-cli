"""Lambda handler for S3 exports bucket events."""

import json
import os


def handler(event, context):
    bucket_name = os.environ.get("BUCKET_NAME", "Unknown")
    records = event.get("Records", [])
    for record in records:
        s3_info = record.get("s3", {})
        key = s3_info.get("object", {}).get("key", "unknown")
        print(f"[{bucket_name}] Object created: {key}")
    return {
        "statusCode": 200,
        "body": json.dumps({
            "bucket": bucket_name,
            "objects_processed": len(records),
        }),
    }
