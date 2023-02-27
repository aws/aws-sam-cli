"""
Hooks Wrapper Class
"""
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, cast

from .exceptions import (
    HookPackageExecuteFunctionalityException,
    InvalidHookWrapperException,
)
from .hook_config import HookPackageConfig

LOG = logging.getLogger(__name__)
INTERNAL_PACKAGES_ROOT = Path(__file__).parent / ".." / ".." / "hook_packages"


class IacHookWrapper:
    """IacHookWrapper

    An IacHookWrapper instance, upon instantiation, looks up the hook package with the specified hook package ID.
    It provides the "prepare" method, which generates an IaC metadata and output the location of the metadata file.

    Example:
    ```
    hook = IacHookWrapper("terraform")
    metadata_loc = hook.prepare("path/to/iac_project", "path/to/output", True)
    ```
    """

    _hook_name: str
    _config: Optional[HookPackageConfig]

    def __init__(self, hook_name: str):
        """
        Parameters
        ----------
        hook_name: str
            Hook name
        """
        self._hook_name = hook_name
        self._config = None
        self._load_hook_package(hook_name)

    def prepare(
        self,
        output_dir_path: str,
        iac_project_path: Optional[str] = None,
        debug: bool = False,
        aws_profile: Optional[str] = None,
        aws_region: Optional[str] = None,
        skip_prepare_infra: bool = False,
    ) -> str:
        """
        Run the prepare hook to generate the IaC Metadata file.

        Parameters
        ----------
        output_dir_path: str
            the path where the hook can create the generated Metadata files. Required
        iac_project_path: str
            the path where the hook can find the TF application. Default value in current work directory.
        debug: bool
            True/False flag to tell the hooks if should print debugging logs or not. Default is False.
        aws_profile: str
            AWS profile to use. Default is None (use default profile)
        aws_region: str
            AWS region to use. Default is None (use default region)
        skip_prepare_infra: bool
            Flag to skip skip prepare hook if we already have the metadata file. Default is False.

        Returns
        -------
        str
            Path to the generated IaC Metadata file
        """
        LOG.info('Executing prepare hook of hook "%s"', self._hook_name)
        params = {
            "IACProjectPath": iac_project_path if iac_project_path else str(Path.cwd()),
            "OutputDirPath": output_dir_path,
            "Debug": debug,
            "SkipPrepareInfra": skip_prepare_infra,
        }
        if aws_profile:
            params["Profile"] = aws_profile
        if aws_region:
            params["Region"] = aws_region

        output = self._execute("prepare", params)

        metadata_file_loc = None
        iac_applications: Dict[str, Dict] = output.get("iac_applications", {})
        if iac_applications and len(iac_applications) == 1:
            # NOTE: we assume there is only one application in the `iac_applications` dictionary,
            # which is the only case we support right now
            main_application = list(iac_applications.values())[0]
            metadata_file_loc = main_application.get("metadata_file")

        if not metadata_file_loc:
            raise InvalidHookWrapperException("Metadata file path not found in the prepare hook output")

        LOG.debug("Metadata file location - %s", metadata_file_loc)
        return cast(str, metadata_file_loc)

    def _load_hook_package(self, hook_name: str) -> None:
        """Find and load hook package config with given hook name

        Parameters
        ----------
        hook_name: str
            Hook name
        """
        # locate hook package from internal first
        LOG.debug("Looking for internal hook package")
        for child in INTERNAL_PACKAGES_ROOT.iterdir():
            if child.name == hook_name:
                LOG.debug('Loaded internal hook package "%s"', hook_name)
                self._config = HookPackageConfig(child)
                return

        raise InvalidHookWrapperException(f'Cannot locate hook package with hook_name "{hook_name}"')

    def _execute(self, functionality_key: str, params: Optional[Dict] = None) -> Dict:
        """
        Execute a functionality with given key

        Parameters
        ----------
        functionality_key: str
            The key of the functionality
        params: Dict
            A dict of parameters to pass into the execution

        Returns
        -------
        Dict
            the output from the execution
        """
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
    """
    Execute a module/method with given module and given method

    Parameters
    ----------
    module: str
        the module where the method lives in
    method: str
        the name of the method to execute
    params: Dict
        A dict of parameters to pass into the execution

    Returns
    -------
    Dict
        the output from the execution
    """
    try:
        mod = importlib.import_module(module)
    except ImportError as e:
        raise InvalidHookWrapperException(f'Import error - HookFunctionality module "{module}"') from e

    if not hasattr(mod, method):
        raise InvalidHookWrapperException(f'HookFunctionality module "{module}" has no method "{method}"')

    result = getattr(mod, method)(params)
    return cast(Dict, result)


def get_available_hook_packages_ids() -> List[str]:
    """
    return a list of available hook names.

    Returns
    -------
    List
        The available hook names.
    """
    LOG.debug("Return available internal hook packages")
    hook_packages_ids = []
    for child in INTERNAL_PACKAGES_ROOT.iterdir():
        if child.is_dir() and child.name[0].isalpha():
            hook_packages_ids.append(child.name)

    return hook_packages_ids
