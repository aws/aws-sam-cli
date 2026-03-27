"""Integration tests for sam remote invoke with durable functions."""

from unittest import TestCase


class TestRemoteInvokeDurable(TestCase):

    def test_remote_invoke_durable_function_basic(self):
        """Test sam remote invoke with durable function.

        Should set the qualifier to $LATEST if not set.
        """
        pass

    def test_remote_invoke_durable_function_with_event(self):
        """Test remote invoke durable function with event data."""
        pass

    def test_remote_invoke_durable_function_async(self):
        """Test remote invoke durable function asynchronously."""
        pass

    def test_remote_invoke_durable_function_override_qualifier(self):
        """Test remote invoke durable function with override qualifier."""
        pass
