"""Unit tests for check_semver_bump.py — the semver-gate logic.

Avoids actual git invocation by passing changed-files lists directly to
the lower-level entrypoint.
"""

from tests.golden import check_semver_bump as csb


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
