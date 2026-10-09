"""Unit tests for check_semver_bump.py — the semver-gate logic.

Avoids actual git invocation by passing changed-files lists directly to
the lower-level entrypoint.
"""

from tests.golden import check_semver_bump as csb

# A rename emits one D + one A change.
_RENAME_CHANGE_COUNT = 2


def test_no_changes_passes():
    rc, msg = csb.check(
        changed=[],
        base_version="1.161.1",
        head_version="1.161.1",
    )
    assert rc == 0


def test_addition_only_does_not_require_bump():
    rc, msg = csb.check(
        changed=[
            csb.Change("tests/golden/templates/x/case_a/expected.build.yaml", "A"),
        ],
        base_version="1.161.1",
        head_version="1.161.1",
    )
    assert rc == 0


def test_modification_without_major_bump_fails():
    rc, msg = csb.check(
        changed=[
            csb.Change("tests/golden/templates/x/case_a/expected.build.yaml", "M"),
        ],
        base_version="1.161.1",
        head_version="1.161.2",
    )
    assert rc != 0
    assert "major" in msg.lower()
    assert "2.0.0" in msg  # suggested next version


def test_modification_with_major_bump_passes():
    rc, msg = csb.check(
        changed=[
            csb.Change("tests/golden/templates/x/case_a/expected.build.yaml", "M"),
        ],
        base_version="1.161.1",
        head_version="2.0.0",
    )
    assert rc == 0


def test_deletion_requires_major_bump():
    rc, msg = csb.check(
        changed=[
            csb.Change("tests/golden/templates/x/case_a/expected.build.yaml", "D"),
        ],
        base_version="1.161.1",
        head_version="1.162.0",
    )
    assert rc != 0


def test_rename_treated_as_delete_plus_add():
    rc, msg = csb.check(
        changed=[
            csb.Change("tests/golden/templates/x/old/expected.build.yaml", "D"),
            csb.Change("tests/golden/templates/x/new/expected.build.yaml", "A"),
        ],
        base_version="1.161.1",
        head_version="1.161.2",
    )
    # The deletion alone forces major; rename is conservative.
    assert rc != 0


def test_parser_rename_emits_delete_plus_add(monkeypatch):
    """A `R<score>\\tOLD\\tNEW` line from `git diff --name-status` must be
    split into a deletion of OLD and an addition of NEW so the gate sees
    the source go away."""
    fake_diff = (
        "R100\ttests/golden/templates/x/old/expected.build.yaml" "\ttests/golden/templates/x/new/expected.build.yaml\n"
    )
    monkeypatch.setattr(csb.subprocess, "check_output", lambda *a, **kw: fake_diff)
    changes = csb._git_changed_files("base", "head")
    assert csb.Change("tests/golden/templates/x/old/expected.build.yaml", "D") in changes
    assert csb.Change("tests/golden/templates/x/new/expected.build.yaml", "A") in changes
    assert len(changes) == _RENAME_CHANGE_COUNT


def test_parser_copy_treated_as_addition_only(monkeypatch):
    """A `C<score>\\tOLD\\tNEW` line means the source still exists, only
    the new target is added. The gate must classify this as A only — not
    let it silently bypass via an unrecognized "C" status."""
    fake_diff = (
        "C100\ttests/golden/templates/x/old/expected.build.yaml" "\ttests/golden/templates/x/new/expected.build.yaml\n"
    )
    monkeypatch.setattr(csb.subprocess, "check_output", lambda *a, **kw: fake_diff)
    changes = csb._git_changed_files("base", "head")
    # Only the new path is reported, classified as A.
    assert changes == [
        csb.Change("tests/golden/templates/x/new/expected.build.yaml", "A"),
    ]


def test_copy_of_existing_pin_does_not_bypass_gate(monkeypatch):
    """End-to-end: even if a copy lands an existing pin's content at a
    new path (status `C100`), the resulting Change list must contain an
    addition — feeding only A's through `check()` correctly returns 0,
    but the path must NOT be silently dropped."""
    fake_diff = (
        "C100\ttests/golden/templates/x/old/expected.build.yaml" "\ttests/golden/templates/x/new/expected.build.yaml\n"
    )
    monkeypatch.setattr(csb.subprocess, "check_output", lambda *a, **kw: fake_diff)
    changes = csb._git_changed_files("base", "head")
    rc, msg = csb.check(changes, base_version="1.161.1", head_version="1.161.1")
    # Addition-only is allowed without a major bump; the key thing is
    # that the change was observed (not silently elided as status "C").
    assert rc == 0
    assert "1 new pin" in msg


def test_changes_outside_corpus_ignored():
    rc, msg = csb.check(
        changed=[
            csb.Change("samcli/lib/foo.py", "M"),
            csb.Change("tests/golden/harness.py", "M"),
        ],
        base_version="1.161.1",
        head_version="1.161.1",
    )
    assert rc == 0


def test_template_yaml_changes_ignored_only_expected_yaml_gates():
    rc, msg = csb.check(
        changed=[
            csb.Change("tests/golden/templates/x/case_a/template.yaml", "M"),
        ],
        base_version="1.161.1",
        head_version="1.161.1",
    )
    assert rc == 0


def test_main_short_circuits_before_reading_versions(monkeypatch, capsys):
    """When no corpus pin changed, main() must NOT call
    _read_version_at_ref. That fn raises on missing samcli/__init__.py
    or unparseable __version__, so on the common-case unrelated PR it
    could fail spuriously. The workflow comment claims 'self-gates' —
    this test asserts main() actually short-circuits."""
    # Diff contains only non-corpus changes.
    fake_diff = "M\tsamcli/lib/foo.py\nM\ttests/golden/harness.py\n"
    monkeypatch.setattr(csb.subprocess, "check_output", lambda *a, **kw: fake_diff)

    def boom(_ref):
        raise AssertionError("_read_version_at_ref must not be called when no corpus pin changed")

    monkeypatch.setattr(csb, "_read_version_at_ref", boom)
    rc = csb.main(["--base", "origin/develop", "--head", "HEAD"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No corpus pin changes" in out


def test_main_reads_versions_when_corpus_pin_changes(monkeypatch):
    """Counterpart: when a corpus pin DID change, main() must read
    versions and run the full check — i.e. the short-circuit doesn't
    over-fire."""
    fake_diff = "M\ttests/golden/templates/x/case_a/expected.build.yaml\n"
    monkeypatch.setattr(csb.subprocess, "check_output", lambda *a, **kw: fake_diff)

    calls = []

    def fake_read(ref):
        calls.append(ref)
        return "1.161.1" if ref == "base" else "2.0.0"

    monkeypatch.setattr(csb, "_read_version_at_ref", fake_read)
    rc = csb.main(["--base", "base", "--head", "head"])
    # Major bump satisfies the gate.
    assert rc == 0
    assert calls == ["base", "head"]
