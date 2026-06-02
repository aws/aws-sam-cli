"""Semver gate: require a major version bump when an existing pinned
golden output is modified or deleted.

Usage (CI):
    python tests/golden/check_semver_bump.py --base origin/develop --head HEAD
"""

from __future__ import annotations

# Allow direct script invocation (`python tests/golden/check_semver_bump.py`)
# in addition to module form (`python -m tests.golden.check_semver_bump`).
# When run as a script, Python does not auto-add the repo root to sys.path,
# so absolute imports rooted at `tests.golden...` would fail. This script
# happens to have no such imports today, but keep the guard symmetrical with
# update_goldens.py so future imports do not silently regress the script form.
if __name__ == "__main__" and __package__ is None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

EXPECTED_GLOB = re.compile(r"^tests/golden/templates/.+/expected\.(build|package)\.yaml$")

# git diff --name-status emits "R<score>\tOLD\tNEW" for renames (3 fields).
_RENAME_DIFF_PARTS = 3


@dataclass(frozen=True)
class Change:
    path: str
    status: str  # "A" added, "M" modified, "D" deleted


def _parse_version(s: str) -> Tuple[int, int, int]:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:.*)?", s.strip())
    if not m:
        raise ValueError(f"unparseable version: {s!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _is_corpus_pin(path: str) -> bool:
    return bool(EXPECTED_GLOB.match(path))


def check(
    changed: List[Change],
    base_version: str,
    head_version: str,
) -> Tuple[int, str]:
    """Return (exit_code, message)."""
    relevant = [c for c in changed if _is_corpus_pin(c.path)]

    if not relevant:
        return 0, "No corpus pin changes; gate passes."

    modifications = [c for c in relevant if c.status == "M"]
    deletions = [c for c in relevant if c.status == "D"]
    additions = [c for c in relevant if c.status == "A"]

    if not (modifications or deletions):
        # Additions only — no bump required.
        return 0, f"{len(additions)} new pin(s); no version bump required."

    base_major, _, _ = _parse_version(base_version)
    head_major, _, _ = _parse_version(head_version)

    if head_major > base_major:
        return 0, "Major version bumped; gate passes."

    suggested = f"{base_major + 1}.0.0"
    summary_lines = [
        "Semver gate FAILED.",
        f"  base version: {base_version}",
        f"  head version: {head_version}",
        f"  required:     major bump (suggested {suggested})",
        "",
        "Reason: an existing pinned golden output was modified or deleted.",
        "  Modifications:",
        *[f"    M  {c.path}" for c in modifications],
        "  Deletions:",
        *[f"    D  {c.path}" for c in deletions],
        "",
        f'To fix: edit samcli/__init__.py and set __version__ = "{suggested}".',
        "If the change is intentional, the major bump signals that to consumers.",
        "If unintentional, run python tests/golden/update_goldens.py --diff to inspect.",
    ]
    return 1, "\n".join(summary_lines)


def _read_version_at_ref(ref: str) -> str:
    """Read __version__ from samcli/__init__.py at a git ref."""
    out = subprocess.check_output(
        ["git", "show", f"{ref}:samcli/__init__.py"], text=True
    )
    m = re.search(r'__version__\s*=\s*"([^"]+)"', out)
    if not m:
        raise RuntimeError(f"cannot find __version__ at {ref}")
    return m.group(1)


def _git_changed_files(base: str, head: str) -> List[Change]:
    """Return all files changed between base and head with their git status."""
    out = subprocess.check_output(
        ["git", "diff", "--name-status", f"{base}...{head}"], text=True
    )
    changes: List[Change] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        # Renames present as "R<score>\tOLD\tNEW" — split into D + A for our purposes.
        if status.startswith("R") and len(parts) == _RENAME_DIFF_PARTS:
            old, new = parts[1], parts[2]
            changes.append(Change(old, "D"))
            changes.append(Change(new, "A"))
        else:
            changes.append(Change(path, status[0]))
    return changes


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="git ref of merge base / target branch")
    parser.add_argument("--head", required=True, help="git ref of PR head")
    args = parser.parse_args(argv)

    changed = _git_changed_files(args.base, args.head)
    base_version = _read_version_at_ref(args.base)
    head_version = _read_version_at_ref(args.head)
    rc, msg = check(changed, base_version, head_version)
    print(msg)
    return rc


if __name__ == "__main__":
    sys.exit(main())
