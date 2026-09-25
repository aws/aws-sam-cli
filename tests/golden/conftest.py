"""Pytest fixtures for the golden-template corpus.

Each case directory under tests/golden/templates/ becomes one parametrized
test ID (relative path), enabling `pytest -k <name>` selection.
"""

from pathlib import Path

TEMPLATES_ROOT = Path(__file__).parent / "templates"


def pytest_generate_tests(metafunc):
    if "golden_case" in metafunc.fixturenames:
        cases = sorted(p.parent for p in TEMPLATES_ROOT.rglob("template.yaml"))
        metafunc.parametrize(
            "golden_case",
            cases,
            ids=lambda p: str(p.relative_to(TEMPLATES_ROOT)),
        )
