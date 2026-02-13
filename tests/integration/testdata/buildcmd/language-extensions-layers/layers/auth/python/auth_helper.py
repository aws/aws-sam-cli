"""Authentication helper utilities."""


def validate_token(token):
    """Validate an authentication token (stub implementation)."""
    if not token:
        return False, "No token provided"
    if not token.startswith("Bearer "):
        return False, "Invalid token format"
    return True, "Token valid"


def get_user_from_token(token):
    """Extract user info from token (stub implementation)."""
    return {
        "user_id": "test-user-001",
        "role": "admin",
    }
