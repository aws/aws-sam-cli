import os
import uuid
import platform
import logging
import venv
import shutil

from tests.testing_utils import run_command


LOG = logging.getLogger(__name__)


class CdkPythonEnv:
    """
    Provides an environment (either using the base Python environment or creating a venv )
    for testing CDK app written in Python
    """

    def __init__(self, base_dir: str, use_venv: bool = False):
        self._base_dir = base_dir
        self._venv_path = os.path.join(self._base_dir, "venv{}".format(str(uuid.uuid4()).replace("-", "")[:5]))
        self._use_venv = use_venv
        if self._use_venv:
            self._create_virtual_env()

    def _create_virtual_env(self) -> None:
        LOG.debug("creating virtual env for testing CDK Python apps")
        try:
            venv.create(
                self._venv_path,
                with_pip=True,
                system_site_packages=False,
                symlinks=False,
            )
        except shutil.SameFileError:
            # SameFileError happens when the python binary in the root env and the virtual env are
            # actually the same file
            # Bypassing it because it does not affect the use of the created virtual env
            pass

    def install_dependencies(self, requirements_path: str) -> None:
        if os.path.exists(requirements_path):
            command = [self.pip_executable, "install", "-r", requirements_path]
            run_command(command_list=command)

    @property
    def python_executable(self) -> str:
        if not self._use_venv:
            return "python"
        if platform.system().lower() == "windows":
            return os.path.join(self._venv_path, "Scripts", "python.exe")
        return os.path.join(self._venv_path, "bin", "python")

    @property
    def pip_executable(self) -> str:
        if not self._use_venv:
            return "pip"
        if platform.system().lower() == "windows":
            return os.path.join(self._venv_path, "Scripts", "pip")
        return os.path.join(self._venv_path, "bin", "pip")
