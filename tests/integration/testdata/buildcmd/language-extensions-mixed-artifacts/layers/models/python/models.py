"""Shared data models."""


class User:
    """User data model."""
    def __init__(self, user_id, name, email=""):
        self.user_id = user_id
        self.name = name
        self.email = email

    def to_dict(self):
        return {"user_id": self.user_id, "name": self.name, "email": self.email}


class Order:
    """Order data model."""
    def __init__(self, order_id, user_id, status="pending"):
        self.order_id = order_id
        self.user_id = user_id
        self.status = status

    def to_dict(self):
        return {"order_id": self.order_id, "user_id": self.user_id, "status": self.status}
