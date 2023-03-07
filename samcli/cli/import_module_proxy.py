"""
Proxy for import module, which can be used to catch dynamic imports which wasn't added to HIDDEN_IMPORTS
to pyinstaller configuration
"""

import importlib
import logging

from samcli.cli import hidden_imports

LOG = logging.getLogger(__name__)


_original_import = importlib.import_module


class MissingDynamicImportError(ImportError):
    """
    Thrown when a dynamic import is used without adding it into hidden imports constant
    """


def _dynamic_import(name, package=None):
    """
    Replaces original import_module function and then analyzes all the imports going through this call.
    If the package is not defined in hidden imports, then it will raise an error
    """
    for hidden_import in hidden_imports.SAM_CLI_HIDDEN_IMPORTS:
        # An import should either match the exact hidden import string or should start with it following a "." (dot)
        # For instance if there is a hidden import definition like 'samtranslator', importing 'samtranslator' or
        # 'samtranslator.sub_module' should succeed. But if there is an import like 'samtranslator_side_module' it
        # should fail.
        if name == hidden_import or name.startswith(f"{hidden_import}."):
            LOG.debug(
                "Importing a package which was already defined in hidden imports name: %s, package: %s", name, package
            )
            return _original_import(name, package)

    LOG.error(
        "Dynamic import (name: %s package: %s) which is not defined in hidden imports: %s",
        name,
        package,
        hidden_imports.SAM_CLI_HIDDEN_IMPORTS,
    )
    raise MissingDynamicImportError(f"Dynamic import not allowed for name: {name} package: {package}")


def attach_import_module_proxy():
    """
    Attaches import_module proxy which will analyze every dynamic import and raise an error if it is not defined in
    hidden imports configuration
    """
    importlib.import_module = _dynamic_import
