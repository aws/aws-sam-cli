"""CLI for regenerating, checking, or diffing pinned golden outputs.

Usage:
    python tests/golden/update_goldens.py                       # regenerate all
    python tests/golden/update_goldens.py --filter 'sam_*/*'    # subset
    python tests/golden/update_goldens.py --check               # dry-run, exit 1 on diff
    python tests/golden/update_goldens.py --diff                # like --check + show unified diff
    python tests/golden/update_goldens.py --new                 # only write missing pins
"""

from __future__ import annotations

# Allow direct script invocation (`python tests/golden/update_goldens.py`)
# in addition to module form (`python -m tests.golden.update_goldens`).
# When run as a script, Python does not auto-add the repo root to sys.path,
# so the absolute `from tests.golden...` imports below would fail. mypy
# treats the __main__ guard as always-False, hence the `type: ignore`.
if __name__ == "__main__" and __package__ is None:
    import sys  # type: ignore[unreachable]  # noqa: E402
    from pathlib import Path  # noqa: E402

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import difflib
import fnmatch
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import yaml

from tests.golden.harness import run_build_and_package
from tests.golden.normalize import normalize

TEMPLATES_ROOT = Path(__file__).parent / "templates"


def _read_metadata(case_dir: Path) -> dict:
    md = case_dir / "metadata.yaml"
    if not md.exists():
        return {}
    with open(md, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_le_default(case_dir: Path, meta: dict) -> bool:
    if "language_extensions" in meta:
        return bool(meta["language_extensions"])
    rel = case_dir.relative_to(TEMPLATES_ROOT)
    return rel.parts[0] == "language_extensions"


def _generate(case_dir: Path) -> Tuple[str, str]:
    """Return (build_yaml, package_yaml) strings for one case."""
    meta = _read_metadata(case_dir)
    le_enabled = _resolve_le_default(case_dir, meta)
    build_dict, pkg_dict = run_build_and_package(case_dir / "template.yaml", language_extensions=le_enabled)
    return normalize(build_dict), normalize(pkg_dict)


def _iter_cases(filter_glob: Optional[str]) -> Iterable[Path]:
    cases = sorted(p.parent for p in TEMPLATES_ROOT.rglob("template.yaml"))
    if not filter_glob:
        yield from cases
        return
    for c in cases:
        rel = str(c.relative_to(TEMPLATES_ROOT))
        if fnmatch.fnmatch(rel, filter_glob):
            yield c


def _existing(case_dir: Path, kind: str) -> Optional[str]:
    p = case_dir / f"expected.{kind}.yaml"
    return p.read_text(encoding="utf-8") if p.exists() else None


def _print_diff(case_rel: str, kind: str, current: Optional[str], generated: str) -> None:
    cur_lines = (current or "").splitlines(keepends=True)
    gen_lines = generated.splitlines(keepends=True)
    diff = difflib.unified_diff(
        cur_lines,
        gen_lines,
        fromfile=f"a/{case_rel}/expected.{kind}.yaml",
        tofile=f"b/{case_rel}/expected.{kind}.yaml",
        lineterm="",
    )
    for line in diff:
        print(line, end="" if line.endswith("\n") else "\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", help="glob applied to case path relative to templates/")
    parser.add_argument("--check", action="store_true", help="dry-run; exit 1 on any diff")
    parser.add_argument("--diff", action="store_true", help="like --check + print unified diff")
    parser.add_argument(
        "--new",
        action="store_true",
        help="only write missing expected.*.yaml; never overwrite existing",
    )
    args = parser.parse_args(argv)

    if args.check and args.new:
        parser.error("--check and --new are mutually exclusive")
    if args.diff and args.new:
        parser.error("--diff and --new are mutually exclusive")
    if args.check and args.diff:
        # The implementation tolerates this (both imply dry_run, --diff
        # wins on output), but the docstring describes them as
        # alternatives. Reject at the parser, symmetric with the --new
        # checks above.
        parser.error("--check and --diff are mutually exclusive")

    dry_run = args.check or args.diff
    any_diff = False

    for case_dir in _iter_cases(args.filter):
        case_rel = str(case_dir.relative_to(TEMPLATES_ROOT))

        # --new fast path: if both pins already exist, skip the build+package
        # pipeline entirely. Only invoke _generate when at least one pin is
        # missing, then write only the missing files.
        if args.new:
            build_existing = _existing(case_dir, "build")
            pkg_existing = _existing(case_dir, "package")
            if build_existing is not None and pkg_existing is not None:
                continue
            build_yaml, pkg_yaml = _generate(case_dir)
            if build_existing is None:
                (case_dir / "expected.build.yaml").write_text(build_yaml, encoding="utf-8")
            if pkg_existing is None:
                (case_dir / "expected.package.yaml").write_text(pkg_yaml, encoding="utf-8")
            continue

        build_yaml, pkg_yaml = _generate(case_dir)

        for kind, generated in (("build", build_yaml), ("package", pkg_yaml)):
            existing = _existing(case_dir, kind)
            if dry_run:
                if existing != generated:
                    any_diff = True
                    if args.diff:
                        _print_diff(case_rel, kind, existing, generated)
                    else:
                        print(f"WOULD CHANGE: {case_rel}/expected.{kind}.yaml")
                continue
            if existing != generated:
                (case_dir / f"expected.{kind}.yaml").write_text(generated, encoding="utf-8")

    if dry_run and any_diff:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
