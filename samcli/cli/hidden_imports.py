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

SAM_CLI_HIDDEN_IMPORTS = list(samcli_modules) + [
    "cookiecutter.extensions",
    "text_unidecode",
    "samtranslator",
    # default hidden import 'pkg_resources.py2_warn' is added
    # since pyInstaller 4.0.
    "pkg_resources.py2_warn",
    "aws_lambda_builders.workflows",
    "configparser",
    "dateparser",
    "jsonschema",
    "cfnlint",
    "networkx.generators",
]
