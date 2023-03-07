"""
Keeps list of hidden/dynamic imports that is being used in SAM CLI, so that pyinstaller can include these packages
"""
import pkgutil
from typing import cast

from typing_extensions import Protocol


class HasPathAndName(Protocol):
    __path__: str
    __name__: str


def walk_modules(module: HasPathAndName, visited: set) -> None:
    """Recursively find all modules from a parent module"""
    for pkg in pkgutil.walk_packages(module.__path__, module.__name__ + "."):
        if pkg.name in visited:
            continue
        visited.add(pkg.name)
        if pkg.ispkg:
            submodule = __import__(pkg.name)
            submodule = cast(HasPathAndName, submodule)
            walk_modules(submodule, visited)


samcli_modules = set(["samcli"])
samcli = __import__("samcli")
samcli = cast(HasPathAndName, samcli)
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
    "dateparser",
    "jsonschema",
    "cfnlint",
]
