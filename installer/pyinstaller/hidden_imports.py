import os
import importlib
import logging
from pathlib import Path
from typing import List


LOG = logging.getLogger(__name__)


def _can_import(module: str) -> bool:
    """Checks if a given module str is import-able"""
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        LOG.debug("Failed to import %s. Skipping.", module)
        return False


def get_samcli_modules() -> List[str]:
    """
    Walks a directory and returns a list of modules
    """
    samcli_root = Path(__file__).parent.parent.parent
    samcli_dir = samcli_root / "samcli"
    modules = []

    for path, _, files in os.walk(samcli_dir):
        module = os.path.relpath(path, samcli_root).replace("/", ".")
        for f in files:
            if f == "__init__.py" and _can_import(module):
                modules.append(module)
            elif f.endswith(".py") and _can_import(module + "." + f[:-3]):
                modules.append(module + "." + f[:-3])

    return modules


SAM_CLI_HIDDEN_IMPORTS = get_samcli_modules() + [
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
