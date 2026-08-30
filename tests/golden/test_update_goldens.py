"""Unit tests for update_goldens.py CLI behavior."""

import shutil
from pathlib import Path

import pytest

from tests.golden import update_goldens

REPO_CASES = Path(__file__).parent / "templates"

# argparse's parser.error() exits with status 2 (Unix convention for usage error).
_ARGPARSE_USAGE_ERROR = 2


@pytest.fixture
def isolated_corpus(tmp_path, monkeypatch):
    """Copy the real corpus to tmp_path and point the CLI at it."""
    dest = tmp_path / "templates"
    shutil.copytree(REPO_CASES, dest)
    monkeypatch.setattr(update_goldens, "TEMPLATES_ROOT", dest)
    return dest


def test_default_regenerates_all_cases(isolated_corpus):
    # Wipe pinned files first, then regenerate
    for p in isolated_corpus.rglob("expected.*.yaml"):
        p.unlink()
    rc = update_goldens.main([])
    assert rc == 0
    # Every case dir now has both expected files
    for case_dir in (p.parent for p in isolated_corpus.rglob("template.yaml")):
        assert (case_dir / "expected.build.yaml").exists()
        assert (case_dir / "expected.package.yaml").exists()


def test_filter_only_regenerates_matching(isolated_corpus):
    # Pre-populate by running a full regen
    update_goldens.main([])
    sam_case = isolated_corpus / "sam_resources" / "serverless_function_zip"
    le_case = isolated_corpus / "language_extensions" / "foreach_static_zip"
    (sam_case / "expected.build.yaml").write_text("STALE\n")
    rc = update_goldens.main(["--filter", "language_extensions/*"])
    assert rc == 0
    # SAM case stays stale
    assert (sam_case / "expected.build.yaml").read_text() == "STALE\n"
    # LE case regenerated
    assert (le_case / "expected.build.yaml").read_text() != "STALE\n"


def test_check_returns_nonzero_when_diff(isolated_corpus):
    update_goldens.main([])  # pin everything fresh
    sam_case = isolated_corpus / "sam_resources" / "serverless_function_zip"
    (sam_case / "expected.build.yaml").write_text("STALE\n")
    rc = update_goldens.main(["--check"])
    assert rc != 0
    # File NOT modified by --check
    assert (sam_case / "expected.build.yaml").read_text() == "STALE\n"


def test_check_returns_zero_when_clean(isolated_corpus):
    update_goldens.main([])
    rc = update_goldens.main(["--check"])
    assert rc == 0


def test_diff_prints_unified_diff(isolated_corpus, capsys):
    update_goldens.main([])
    sam_case = isolated_corpus / "sam_resources" / "serverless_function_zip"
    (sam_case / "expected.build.yaml").write_text("STALE\n")
    rc = update_goldens.main(["--diff"])
    assert rc != 0
    out = capsys.readouterr().out
    assert "STALE" in out
    assert "---" in out and "+++" in out


def test_new_only_writes_missing_pins(isolated_corpus):
    sam_case = isolated_corpus / "sam_resources" / "serverless_function_zip"
    # Pre-pin everything
    update_goldens.main([])
    # Wipe just one file
    (sam_case / "expected.build.yaml").unlink()
    # Add an unrelated stale modification to a *different* case
    le_case = isolated_corpus / "language_extensions" / "foreach_static_zip"
    le_pin = le_case / "expected.build.yaml"
    le_pin.write_text("STALE\n")
    rc = update_goldens.main(["--new"])
    assert rc == 0
    # SAM case now has the file back
    assert (sam_case / "expected.build.yaml").exists()
    # LE case stays stale (--new does not touch existing pins)
    assert le_pin.read_text() == "STALE\n"


def test_new_short_circuits_when_all_pins_exist(isolated_corpus, monkeypatch):
    """When every case is fully pinned, --new must not invoke _generate."""
    # Pre-pin everything (uses real _generate).
    update_goldens.main([])

    # Now poison _generate so a single call would blow up.
    def boom(*_args, **_kwargs):
        raise AssertionError("_generate must not be called when all pins exist under --new")

    monkeypatch.setattr(update_goldens, "_generate", boom)
    rc = update_goldens.main(["--new"])
    assert rc == 0


def test_check_and_diff_are_mutually_exclusive(capsys):
    """--check and --diff are documented as alternatives. Reject the
    combination at the parser, symmetric with the existing --new mutex
    checks."""
    with pytest.raises(SystemExit) as excinfo:
        update_goldens.main(["--check", "--diff"])
    assert excinfo.value.code == _ARGPARSE_USAGE_ERROR
    err = capsys.readouterr().err
    assert "--check and --diff are mutually exclusive" in err
