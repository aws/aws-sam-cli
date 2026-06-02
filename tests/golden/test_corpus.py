"""Golden corpus: byte-exact diff for build + package output per case."""

from pathlib import Path

from tests.golden.harness import run_build_pipeline, run_package_pipeline
from tests.golden.normalize import normalize
from tests.golden.update_goldens import _read_metadata, _resolve_le_default

TEMPLATES_ROOT = Path(__file__).parent / "templates"


def _hint(case_dir: Path) -> str:
    rel = case_dir.relative_to(TEMPLATES_ROOT)
    return (
        f"\nGolden mismatch in {rel}.\n"
        f"To inspect:   python tests/golden/update_goldens.py --diff --filter '{rel}'\n"
        f"To re-pin:    python tests/golden/update_goldens.py --filter '{rel}'\n"
        f"If intentional:\n"
        f"  - new case (added expected.*.yaml)         -> no version bump at PR time\n"
        f"  - modified/deleted existing expected.*     -> bump major in samcli/__init__.py\n"
    )


def test_build_output_matches_golden(golden_case):
    meta = _read_metadata(golden_case)
    le_enabled = _resolve_le_default(golden_case, meta)
    actual = normalize(
        run_build_pipeline(golden_case / "template.yaml", language_extensions=le_enabled)
    )
    expected_path = golden_case / "expected.build.yaml"
    assert expected_path.exists(), f"missing {expected_path}; run update_goldens.py --new"
    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected, _hint(golden_case)


def test_package_output_matches_golden(golden_case):
    meta = _read_metadata(golden_case)
    le_enabled = _resolve_le_default(golden_case, meta)
    build_out = run_build_pipeline(
        golden_case / "template.yaml", language_extensions=le_enabled
    )
    actual = normalize(run_package_pipeline(golden_case / "template.yaml", build_out))
    expected_path = golden_case / "expected.package.yaml"
    assert expected_path.exists(), f"missing {expected_path}; run update_goldens.py --new"
    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected, _hint(golden_case)
