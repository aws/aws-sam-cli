"""
Keeps list of hidden/dynamic imports that is being used in SAM CLI, so that pyinstaller can include these packages
"""

import pkgutil
from types import ModuleType


def walk_modules(module: ModuleType, visited: set) -> None:
    """Recursively find all modules from a parent module"""
    for pkg in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
        if pkg.name in visited:
            continue
        visited.add(pkg.name)
        if pkg.ispkg:
            submodule = __import__(pkg.name)
            walk_modules(submodule, visited)


samcli_modules = set(["samcli"])
samcli = __import__("samcli")
walk_modules(samcli, samcli_modules)

# sorted(), not list(): set iteration order for strings varies between processes because
# string hashing is randomized, so list() gave this module a different order on every
# interpreter. That made pyinstaller's hidden-import list unstable between builds, and
# made the parameterized test over it collect in a different order in each pytest-xdist
# worker ("Different tests were collected between workers"). Order is not meaningful to
# pyinstaller, so sorting is free.
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
