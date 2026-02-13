"""Lambda worker for PaymentProcessing state machine."""

import json
import os


def handler(event, context):
    workflow_name = os.environ.get("WORKFLOW_NAME", "Unknown")
    action = event.get("action", "unknown")
    payload = event.get("payload", {})
    print(f"[{workflow_name}] Action: {action}, Payload: {json.dumps(payload)}")
    return {
        "workflow": workflow_name,
        "action": action,
        "status": "completed",
        "payload": payload,
    }
