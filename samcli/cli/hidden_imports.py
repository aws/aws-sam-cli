"""
Keeps list of hidden/dynamic imports that is being used in SAM CLI, so that pyinstaller can include these packages
"""

import pkgutil
from types import ModuleType
from typing import List


def walk_modules(module: ModuleType, visited: List[str]) -> None:
    """Recursively find all modules from a parent module"""
    for pkg in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
        if pkg.name in visited:
            continue
        visited.append(pkg.name)
        if pkg.ispkg:
            submodule = __import__(pkg.name)
            walk_modules(submodule, visited)


samcli_modules = ["samcli"]
samcli = __import__("samcli")
walk_modules(samcli, samcli_modules)

# sorted(), not the raw collection order: this list is what pyinstaller bundles, and an
# unstable order made builds non-reproducible and made the parameterized test over it
# collect differently in each pytest-xdist worker ("Different tests were collected
# between workers"). pkgutil.walk_packages happens to yield sorted names today, but that
# is an implementation detail of its os.listdir().sort(), so sort explicitly rather than
# depend on it. Order is not meaningful to pyinstaller, so this is free.
SAM_CLI_HIDDEN_IMPORTS = sorted(samcli_modules) + [
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
