"""
Hooks Wrapper Class
"""
from doctest import OutputChecker
import json
import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any


from .hook_config import HookPackageConfig, HookFunctionality
from .exceptions import (
    InvalidHookPackageException,
    InvalidHookPackageConfigException,
    InvalidHookWrapperException,
    HookPackageExecuteFunctionalityException,
)


LOG = logging.getLogger(__name__)


class IacHookWrapper:
    """IacHookWrapper"""

    _config: HookPackageConfig

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

    def _execute(self, functionality_key: str, params: Optional[Dict] = None) -> Optional[Any]:
        if functionality_key not in self._config.functionalities:
            raise HookPackageExecuteFunctionalityException(
                f'Functionality "{functionality_key}" is not defined in the hook package.'
            )

        functionality = self._config.functionalities[functionality_key]
        entry_script = self._get_entry_script_executable(functionality)
        command = [entry_script]
        if params:
            if functionality.parameters:
                self._validate_params(functionality, params)
            json_str = json.dumps(params)
            command.append(json_str)

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                encoding="utf-8",
            )
            with process.stderr:
                for line in process.stderr.readlines():
                    LOG.info(line)

            with process.stdout:
                output = json.load(process.stdout.read())

            return output
        except subprocess.TimeoutExpired:
            LOG.error("Command: %s, TIMED OUT", command)
            LOG.error()
            process.kill()
            return {}

    def _get_entry_script_executable(self, functionality: HookFunctionality) -> str:
        entry_script = functionality.entry_script
        if platform.system().lower() == "windows":
            entry_script += ".bat"
        else:
            entry_script += ".sh"
        entry_script = self._config.package_dir / entry_script
        return str(entry_script.resolve())

    def _validate_params(self, functionality: HookFunctionality, provided_params: Dict) -> None:
        # check for missing mandatory params
        missing_params = [
            param.long_name
            for param in functionality.mandatory_parameters
            if param.long_name not in provided_params and param.short_name not in provided_params
        ]
        if missing_params:
            raise InvalidHookWrapperException(f"Missing required parameters {', '.join(missing_params)}")
