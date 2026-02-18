"""Root conftest for integration/unit tests."""
import pytest
import os


if "__SAM_CLI_TELEMETRY_ENDPOINT_URL" not in os.environ:
    os.environ["__SAM_CLI_TELEMETRY_ENDPOINT_URL"] = ""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_credential: mark test as requiring AWS credentials (skipped in local-only CI jobs)",
    )
