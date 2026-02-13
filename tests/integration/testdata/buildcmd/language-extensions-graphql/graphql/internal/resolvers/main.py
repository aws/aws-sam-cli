"""Lambda resolver for internal GraphQL API."""

import json
import os


def handler(event, context):
    api_name = os.environ.get("API_NAME", "Unknown")
    field = event.get("fieldName", "unknown")
    arguments = event.get("arguments", {})
    print(f"[{api_name}] Resolving: {field} with args: {json.dumps(arguments)}")

    if field == "getUser":
        return {
            "id": arguments.get("id", "1"),
            "name": "Alice",
            "email": "alice@example.com",
            "role": "admin",
            "createdAt": "2025-01-01T00:00:00Z",
            "lastLogin": "2025-02-20T12:00:00Z",
        }
    elif field == "listUsers":
        return [
            {
                "id": "1", "name": "Alice", "email": "alice@example.com",
                "role": "admin", "createdAt": "2025-01-01T00:00:00Z",
                "lastLogin": "2025-02-20T12:00:00Z",
            },
            {
                "id": "2", "name": "Bob", "email": "bob@example.com",
                "role": "viewer", "createdAt": "2025-01-15T00:00:00Z",
                "lastLogin": "2025-02-19T08:00:00Z",
            },
        ]
    elif field == "getAuditLog":
        return {
            "id": arguments.get("id", "1"),
            "action": "USER_LOGIN",
            "userId": "1",
            "timestamp": "2025-02-20T12:00:00Z",
            "details": "Successful login from 192.168.1.1",
        }
    elif field == "listAuditLogs":
        return [
            {"id": "1", "action": "USER_LOGIN", "userId": "1",
             "timestamp": "2025-02-20T12:00:00Z", "details": "Login"},
            {"id": "2", "action": "USER_UPDATE", "userId": "2",
             "timestamp": "2025-02-20T11:00:00Z", "details": "Role change"},
        ]
    elif field == "updateUserRole":
        return {
            "id": arguments.get("userId", "1"),
            "name": "Alice",
            "email": "alice@example.com",
            "role": arguments.get("role", "viewer"),
            "createdAt": "2025-01-01T00:00:00Z",
            "lastLogin": "2025-02-20T12:00:00Z",
        }
    elif field == "deleteUser":
        return True

    return None
