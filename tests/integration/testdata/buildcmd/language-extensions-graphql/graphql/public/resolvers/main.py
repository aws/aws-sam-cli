"""Lambda resolver for public GraphQL API."""

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
        }
    elif field == "listUsers":
        return [
            {"id": "1", "name": "Alice", "email": "alice@example.com"},
            {"id": "2", "name": "Bob", "email": "bob@example.com"},
        ]
    elif field == "getProduct":
        return {
            "id": arguments.get("id", "1"),
            "name": "Widget",
            "price": 9.99,
            "inStock": True,
        }
    elif field == "listProducts":
        return [
            {"id": "1", "name": "Widget", "price": 9.99, "inStock": True},
            {"id": "2", "name": "Gadget", "price": 19.99, "inStock": False},
        ]
    elif field == "createUser":
        inp = arguments.get("input", {})
        return {
            "id": "new-user-001",
            "name": inp.get("name", "Unknown"),
            "email": inp.get("email", ""),
        }

    return None
