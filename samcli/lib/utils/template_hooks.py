"""
Reject cookiecutter template hooks that this SAM CLI installation cannot run.

Cookiecutter runs a Python hook with ``sys.executable``. In a PyInstaller bundle that is the sam
executable rather than an interpreter, so the hook cannot run and cookiecutter is told it succeeded.
Refusing instead means a template whose hook matters fails loudly rather than producing a project
that is quietly missing whatever the hook was meant to do.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

from cookiecutter import hooks
from cookiecutter import main as cookiecutter_main
from cookiecutter.exceptions import FailedHookException
from cookiecutter.utils import work_in

from samcli.lib.utils.subprocess_utils import is_pyinstaller_bundle

LOG = logging.getLogger(__name__)

UNSUPPORTED_HOOK_MESSAGE = (
    "Cannot run the template hook {hook}: this SAM CLI installation has no Python interpreter "
    "available to run it. To unblock, either re-install SAM CLI from pip, or remove the hook from "
    "the project."
)


class UnsupportedTemplateHookError(FailedHookException):
    """A template's Python hook cannot be run by this installation.

    Subclasses cookiecutter's own hook failure so that cookiecutter still removes the partially
    generated project.
    """


def _reject_python_hook(script_path: str) -> None:
    """Raise if the hook is a Python script, which needs an interpreter this install lacks."""
    if not script_path.endswith(".py"):
        return
    hook = os.path.basename(script_path)
    LOG.debug("Refusing to run template hook %s from a PyInstaller bundle", script_path)
    raise UnsupportedTemplateHookError(UNSUPPORTED_HOOK_MESSAGE.format(hook=hook))


@contextmanager
def guarded_template_hooks() -> Iterator[None]:
    """Reject Python template hooks for the duration of a cookiecutter call; no-op when not bundled.

    pre_gen_project and post_gen_project arrive through run_script_with_context, which still knows
    the hook's real name rather than the temporary copy run_script is handed. pre_prompt is checked
    before cookiecutter runs it, because cookiecutter replaces a pre_prompt failure with a message
    of its own that would hide the remedy. run_script stays wrapped as a backstop.
    """
    if not is_pyinstaller_bundle():
        yield
        return

    original_run_script = hooks.run_script
    original_run_script_with_context = hooks.run_script_with_context
    original_run_pre_prompt_hook = cookiecutter_main.run_pre_prompt_hook

    def run_script(script_path: str, cwd: str = ".") -> None:
        _reject_python_hook(script_path)
        original_run_script(script_path, cwd)

    def run_script_with_context(script_path: str, cwd: str, context: dict) -> None:
        _reject_python_hook(script_path)
        original_run_script_with_context(script_path, cwd, context)

    # Typed loosely because both the argument and the return are forwarded to untyped cookiecutter.
    def run_pre_prompt_hook(repo_dir: Any) -> Any:
        with work_in(repo_dir):
            for script in hooks.find_hook("pre_prompt") or []:
                _reject_python_hook(script)
        return original_run_pre_prompt_hook(repo_dir)

    # cookiecutter logs a hook failure with logger.exception before re-raising, which would print a
    # traceback ahead of the remedy. Filtered by level rather than by propagation, because a logger
    # with no handlers of its own falls back to logging.lastResort and still reaches stderr.
    hooks_logger = logging.getLogger(hooks.__name__)
    original_level = hooks_logger.level

    hooks.run_script = run_script
    hooks.run_script_with_context = run_script_with_context
    cookiecutter_main.run_pre_prompt_hook = run_pre_prompt_hook
    hooks_logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        hooks.run_script = original_run_script
        hooks.run_script_with_context = original_run_script_with_context
        cookiecutter_main.run_pre_prompt_hook = original_run_pre_prompt_hook
        hooks_logger.setLevel(original_level)
