"""
Proxy for import module, which can be used to catch dynamic imports which wasn't added to HIDDEN_IMPORTS
to pyinstaller configuration
"""

import importlib
import logging

from samcli.cli import hidden_imports

LOG = logging.getLogger(__name__)


_original_import = importlib.import_module


def _dynamic_import(name, package=None):
    if name in hidden_imports.SAM_CLI_HIDDEN_IMPORTS:
        LOG.debug(
            "Importing a package which was already defined in hidden imports name: %s, package: %s", name, package
        )
        return _original_import(name, package)
    if not name.startswith('samcli.'):
        LOG.debug("Importing a package from 'samcli.' module name: %s, package: %s", name, package)
        return _original_import(name, package)

    LOG.info("Dynamic import name: %s package: %s, which is not defined in hidden imports", name, package)
    raise ValueError(f'Dynamic import not allowed for {name} {package}')


def attach_module_import_proxy():
    importlib.import_module = _dynamic_import
