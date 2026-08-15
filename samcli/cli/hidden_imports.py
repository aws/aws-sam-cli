"""
Keeps list of hidden/dynamic imports that is being used in SAM CLI, so that pyinstaller can include these packages
"""

import pkgutil
from types import ModuleType
from typing import List, Optional, Set


def walk_modules(module: ModuleType, visited: List[str], seen: Optional[Set[str]] = None) -> None:
    """Recursively find all modules from a parent module.

    `visited` keeps discovery order, which callers rely on: it is what pyinstaller
    bundles, and an unstable order both makes builds non-reproducible and makes the
    parameterized test over it collect differently in each pytest-xdist worker.

    `seen` is a parallel set used only for the dedup check, so ordering does not cost
    O(n) lookups. That matters because `__import__("samcli.cli")` returns the top-level
    `samcli`, so each recursive call re-walks the whole tree from the root -- 108k
    membership checks for 658 modules. Optional so existing two-argument callers work.
    """
    if seen is None:
        seen = set(visited)
    for pkg in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
        if pkg.name in seen:
            continue
        seen.add(pkg.name)
        visited.append(pkg.name)
        if pkg.ispkg:
            submodule = __import__(pkg.name)
            walk_modules(submodule, visited, seen)


samcli_modules = ["samcli"]
samcli = __import__("samcli")
walk_modules(samcli, samcli_modules)

# Collected in discovery order. This used to be list(set(...)), whose order varied per
# process because string hashing is randomized -- that made pyinstaller's bundle list
# unstable between builds, and made the parameterized test over it collect differently in
# each pytest-xdist worker ("Different tests were collected between workers"). Walking
# into a list is deterministic on its own, so no sort is needed here; the ordering is
# pinned by test_walk_modules_order_is_deterministic_and_sorted.
SAM_CLI_HIDDEN_IMPORTS = samcli_modules + [
    "cookiecutter.extensions",
    "text_unidecode",
    "samtranslator",
    "aws_lambda_builders.workflows",
    "configparser",
    "dateparser",
    "jsonschema",
    "cfnlint",
    "networkx.generators",
]
