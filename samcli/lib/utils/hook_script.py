"""
Support for running cookiecutter template hooks from a PyInstaller bundle.

Cookiecutter runs a Python hook as ``[sys.executable, script]``. In a bundle ``sys.executable`` is
the sam executable itself, so the hook never runs. This module supplies a real interpreter: a system
python3 when one is available, otherwise this executable re-launched in hook mode.
"""

import logging
import os
import runpy
import shutil
import subprocess
import sys
from contextlib import contextmanager
from types import ModuleType
from typing import Iterator, Optional

from samcli.lib.utils.subprocess_utils import is_pyinstaller_bundle, isolate_library_paths_for_subprocess

LOG = logging.getLogger(__name__)

# Set on the hook subprocess so a re-launched bundle runs the script instead of parsing a command name.
HOOK_SCRIPT_ENV_VAR = "SAM_CLI_RUN_HOOK_SCRIPT"

# A bundle ships no interpreter of its own. A system one is preferred for isolation, so that SAM's
# bundled dependencies do not become an implicit contract for template authors -- not for fidelity
# with a pip install, where hooks can in fact import SAM's dependencies. The order matches
# _get_python_command_name in the terraform prepare hook, and includes the Windows launcher because
# a default python.org install puts only py.exe on PATH.
_INTERPRETER_CANDIDATES = ("python3", "py3", "python", "py")
# Matches requires-python, so a hook never sees an older Python than a pip install would give it.
_MINIMUM_PYTHON_VERSION = (3, 10)
_PROBE_TIMEOUT = 10


def run_hook_script_if_requested() -> None:
    """Run the script named in argv and exit, when re-launched by the patched hook runner."""
    # Popped rather than read so a hook that shells out to sam again gets the normal CLI.
    requested = os.environ.pop(HOOK_SCRIPT_ENV_VAR, None) == "1"
    arguments = sys.argv[1:]
    if not requested or not arguments:
        return

    LOG.debug("Running template hook script %s through this executable", arguments[0])
    # The bootloader re-points library paths into the bundle for this process, and the CLI callback
    # that normally undoes that is never reached here. Hooks routinely shell out to git, npm and pip.
    isolate_library_paths_for_subprocess()
    # A hook launched by a real interpreter sees only its own path in argv; run_path fixes argv[0]
    # but would leave our second argument behind, so give the hook the argv it expects.
    with _replaced_attribute(sys, "argv", [arguments[0]]):
        runpy.run_path(arguments[0], run_name="__main__")
    sys.exit(0)


def find_system_interpreter() -> Optional[str]:
    """Return the path to a usable system Python 3, or None if there isn't one."""
    for candidate in _INTERPRETER_CANDIDATES:
        path = shutil.which(candidate)
        if not path or os.path.realpath(path) == os.path.realpath(sys.executable):
            continue
        # Executed rather than trusted because Windows ships a "python" App Execution Alias that
        # resolves on PATH without being an interpreter, and because /usr/bin/python3 is 3.6 on
        # older distributions, where a hook using newer syntax would fail with a SyntaxError.
        try:
            completed = subprocess.run(
                [path, "-c", f"import sys; sys.exit(0 if sys.version_info >= {_MINIMUM_PYTHON_VERSION} else 1)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=_PROBE_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0:
            return path
    return None


@contextmanager
def _replaced_attribute(target: object, name: str, value: object) -> Iterator[None]:
    """Set an attribute for the duration of the block, restoring whatever was there before."""
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


@contextmanager
def _hook_script_env() -> Iterator[None]:
    """Mark the environment so the re-launched executable runs the hook script."""
    original = os.environ.get(HOOK_SCRIPT_ENV_VAR)
    os.environ[HOOK_SCRIPT_ENV_VAR] = "1"
    try:
        yield
    finally:
        if original is None:
            os.environ.pop(HOOK_SCRIPT_ENV_VAR, None)
        else:
            os.environ[HOOK_SCRIPT_ENV_VAR] = original


@contextmanager
def patched_hook_runner(hooks_module: ModuleType) -> Iterator[None]:
    """Make cookiecutter's Python hooks runnable while frozen; a no-op when not frozen.

    The module is passed in so this stays importable without pulling in cookiecutter, which every
    sam invocation would otherwise pay for at startup.
    """
    if not is_pyinstaller_bundle():
        yield
        return

    original_run_script = hooks_module.run_script

    def run_script(script_path: str, cwd: str = ".") -> None:
        # Only .py hooks go through an interpreter; anything else already runs on its own.
        if not script_path.endswith(".py"):
            original_run_script(script_path, cwd)
            return

        interpreter = find_system_interpreter()
        if interpreter:
            LOG.debug("Running template hook with system interpreter %s", interpreter)
            with _replaced_attribute(sys, "executable", interpreter):
                original_run_script(script_path, cwd)
            return

        LOG.debug("No system interpreter found, re-launching this executable to run the template hook")
        with _hook_script_env():
            original_run_script(script_path, cwd)

    with _replaced_attribute(hooks_module, "run_script", run_script):
        yield
