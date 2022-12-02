import importlib
import pkgutil
import logging
from pathlib import Path
from types import ModuleType

import samcli


LOG = logging.getLogger(__name__)
samcli_root = Path(__file__).parent.parent.parent


def walk_modules(module: ModuleType, visited: set) -> None:
    """Recursively find all modules from a parent module"""
    for pkg in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
        if pkg.name in visited:
            continue
        visited.add(pkg.name)
        if pkg.ispkg:
            submodule = importlib.import_module(pkg.name)
            walk_modules(submodule, visited)

samcli_modules = set(["samcli"])
walk_modules(samcli, samcli_modules)

SAM_CLI_HIDDEN_IMPORTS = list(samcli_modules) + [
    "cookiecutter.extensions",
    "jinja2_time",
    "text_unidecode",
    "samtranslator",
    # default hidden import 'pkg_resources.py2_warn' is added
    # since pyInstaller 4.0.
    "pkg_resources.py2_warn",
    "aws_lambda_builders.workflows",
    "configparser",
]
