"""
Hooks Wrapper Class
"""
import logging
import importlib
from pathlib import Path
from typing import Optional, Dict, cast


from .hook_config import HookPackageConfig
from .exceptions import (
    InvalidHookPackageConfigException,
    InvalidHookWrapperException,
    HookPackageExecuteFunctionalityException,
)


LOG = logging.getLogger(__name__)


class IacHookWrapper:
    """IacHookWrapper"""

    _config: Optional[HookPackageConfig]

    _INTERNAL_PACKAGES_ROOT = Path(__file__).parent / ".." / ".." / "hook_packages"

    def __init__(self, hook_package_id: str):
        self._config = None
        self._load_hook_package(hook_package_id)

    def prepare(
        self,
        iac_project_path: str,
        output_dir_path: str,
        debug: bool = False,
        logs_path: Optional[str] = None,
        aws_profile: Optional[str] = None,
        aws_region: Optional[str] = None,
    ):
        params = {
            "IACProjectPath": iac_project_path if iac_project_path else str(Path.cwd()),
            "OutputDirPath": output_dir_path,
            "Debug": debug,
        }
        if logs_path:
            params["LogsPath"] = logs_path

        output = self._execute("prepare", params)
        return output

    def _load_hook_package(self, hook_package_id: str) -> None:
        # locate hook package from internal first
        for child in self._INTERNAL_PACKAGES_ROOT.iterdir():
            try:
                hook_package_config = HookPackageConfig(child)
                if hook_package_config.package_id == hook_package_id:
                    self._config = hook_package_config
                    return
            except InvalidHookPackageConfigException:
                continue

        if not self._config:
            raise InvalidHookWrapperException(f'Cannot locate hook package with hook_package_id "{hook_package_id}"')

    def _execute(self, functionality_key: str, params: Optional[Dict] = None) -> Dict:
        if not self._config:
            raise InvalidHookWrapperException("Config is missing. You must instantiate a hook with a valid config")

        if functionality_key not in self._config.functionalities:  # pylint: disable=unsupported-membership-test
            raise HookPackageExecuteFunctionalityException(
                f'Functionality "{functionality_key}" is not defined in the hook package'
            )

        functionality = self._config.functionalities[functionality_key]
        if functionality.entry_method:
            return _execute_as_module(functionality.module, functionality.method, params)

        raise InvalidHookWrapperException(f'Functionality "{functionality_key}" is missing an "entry_method"')


def _execute_as_module(module: str, method: str, params: Optional[Dict] = None) -> Dict:
    try:
        mod = importlib.import_module(module)
    except ImportError as e:
        raise InvalidHookWrapperException(f'Import error - HookFunctionality module "{module}"') from e

    if not hasattr(mod, method):
        raise InvalidHookWrapperException(f'HookFunctionality module "{module}" has no method "{method}"')

    result = getattr(mod, method)(params)
    return cast(Dict, result)
