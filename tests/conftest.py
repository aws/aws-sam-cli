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
    config.addinivalue_line(
        "markers",
        "tier1: cross-platform smoke tests that run on every OS/container-runtime combination",
    )
    config.addinivalue_line(
        "markers",
        "tier1_extra: parameterized expansions of tier1 tests (excluded from normal CI, included in tier1 jobs)",
    )
