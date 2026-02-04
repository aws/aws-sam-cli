"""
Utils for invoking subprocess calls
"""

import logging
import os
import platform
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from subprocess import PIPE, STDOUT, Popen
from time import sleep
from typing import Any, AnyStr, Callable, Dict, List, Optional, Union

from samcli.commands.exceptions import UserException
from samcli.lib.utils.stream_writer import StreamWriter

# Environment variables that control library loading paths
# These are set by PyInstaller and can cause conflicts with system binaries
LIBRARY_PATH_VARS = [
    "LD_LIBRARY_PATH",  # Linux
    "DYLD_LIBRARY_PATH",  # macOS
    "DYLD_FALLBACK_LIBRARY_PATH",  # macOS fallback
    "DYLD_FRAMEWORK_PATH",  # macOS frameworks
]

# Original library paths before cleanup (stored for debugging/restoration if needed)
# Using a mutable container to avoid global statement (PLW0603)
_library_path_state: Dict[str, Optional[Dict[str, str]]] = {"original_library_paths": None}

# These are the bytes that used as a prefix for a some string to color them in red to show errors.
TERRAFORM_ERROR_PREFIX = [27, 91, 51, 49]

IS_WINDOWS = platform.system().lower() == "windows"
LOG = logging.getLogger(__name__)


class LoadingPatternError(UserException):
    def __init__(self, ex):
        self.ex = ex
        message_fmt = f"Failed to execute the subprocess. {ex}"
        super().__init__(message=message_fmt)


def default_loading_pattern(stream_writer: Optional[StreamWriter] = None, loading_pattern_rate: float = 0.5) -> None:
    """
    A loading pattern that just prints '.' to the terminal

    Parameters
    ----------
    stream_writer: Optional[StreamWriter]
        The stream to which to write the pattern
    loading_pattern_rate: int
        How frequently to generate the pattern
    """
    stream_writer = stream_writer or StreamWriter(sys.stderr)
    stream_writer.write_str(".")
    stream_writer.flush()
    sleep(loading_pattern_rate)


def invoke_subprocess_with_loading_pattern(
    command_args: Dict[str, Any],
    loading_pattern: Callable[[StreamWriter], None] = default_loading_pattern,
    stream_writer: Optional[StreamWriter] = None,
    is_running_terraform_command: Optional[bool] = None,
) -> Optional[Union[str, bytes]]:
    """
    Wrapper for Popen to asynchronously invoke a subprocess while
    printing a given pattern until the subprocess is complete.
    If the log level is lower than INFO, stream the process stdout instead.

    Parameters
    ----------
    command_args: Dict[str, Any]
        The arguments to give to the Popen call, should contain at least one parameter "args"
    loading_pattern: Callable[[StreamWriter], None]
        A function generating a pattern to the given stream
    stream_writer: Optional[StreamWriter]
        The stream to which to write the pattern
    is_running_terraform_command: Optional[bool]
        Flag to refer if the subprocess is for Terraform commands. This flag is used to help reading the subprocess
        errors in case of windows.

    Returns
    -------
    str
        A string containing the process output
    """
    stream_writer = stream_writer or StreamWriter(sys.stderr)
    process_output = ""
    process_stderr = ""

    # Default stdout to PIPE if not specified so
    # that output isn't printed along with dots
    if not command_args.get("stdout"):
        command_args["stdout"] = PIPE

    if not command_args.get("stderr"):
        command_args["stderr"] = STDOUT if IS_WINDOWS else PIPE

    try:
        keep_printing = LOG.getEffectiveLevel() >= logging.INFO

        def _print_loading_pattern():
            while keep_printing:
                loading_pattern(stream_writer)

        # Popen is async as opposed to run, so we can print while we wait
        with Popen(**command_args) as process:
            with ThreadPoolExecutor() as executor:
                executor.submit(_print_loading_pattern)

                if process.stdout:
                    # Logging level is DEBUG, streaming logs instead
                    # we read from subprocess stdout to avoid the deadlock process.wait function
                    # for more detail check this python bug https://bugs.python.org/issue1256
                    for line in process.stdout:
                        is_error = (
                            is_running_terraform_command
                            and IS_WINDOWS
                            and len(line) >= len(TERRAFORM_ERROR_PREFIX)
                            and line[0:4] == bytes(TERRAFORM_ERROR_PREFIX)
                        )
                        decoded_line = _check_and_process_bytes(line, preserve_whitespace=is_error)
                        if LOG.getEffectiveLevel() < logging.INFO:
                            LOG.debug(decoded_line)
                        if not is_error:
                            process_output += decoded_line
                        else:
                            process_stderr += decoded_line

                if process.stderr:
                    for line in process.stderr:
                        # Since we typically log standard error back, we preserve
                        # the whitespace so that it is formatted correctly
                        decoded_line = _check_and_process_bytes(line, preserve_whitespace=True)
                        process_stderr += decoded_line

                return_code = process.wait()
                keep_printing = False

                stream_writer.write_str(os.linesep)
                stream_writer.flush()

                if return_code:
                    raise LoadingPatternError(
                        f"The process {command_args.get('args', [])} returned a "
                        f"non-zero exit code {process.returncode}.\n{process_stderr}"
                    )

    except (OSError, ValueError) as e:
        raise LoadingPatternError(f"Subprocess execution failed {command_args.get('args', [])}. {e}") from e

    return process_output


def _check_and_process_bytes(check_value: AnyStr, preserve_whitespace=False) -> str:
    if isinstance(check_value, bytes):
        decoded_value = check_value.decode("utf-8")
        if preserve_whitespace:
            return decoded_value
        return decoded_value.strip()
    return check_value


def is_pyinstaller_bundle() -> bool:
    """
    Check if SAM CLI is running from a PyInstaller bundle.

    PyInstaller sets the '_MEIPASS' attribute on the sys module to point
    to the temporary directory where bundled files are extracted.

    Returns
    -------
    bool
        True if running from a PyInstaller bundle, False otherwise.
    """
    return hasattr(sys, "_MEIPASS")


def get_pyinstaller_lib_path() -> Optional[str]:
    """
    Get the PyInstaller internal library path if running from a bundle.

    Returns
    -------
    Optional[str]
        The path to PyInstaller's internal libraries, or None if not in a bundle.
    """
    if is_pyinstaller_bundle():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return os.path.join(meipass, "_internal")
    return None


def _save_original_library_paths() -> None:
    """Save original library path values before modification."""
    if _library_path_state["original_library_paths"] is None:
        original_paths: Dict[str, str] = {}
        for var in LIBRARY_PATH_VARS:
            if var in os.environ:
                original_paths[var] = os.environ[var]
        _library_path_state["original_library_paths"] = original_paths


def _filter_pyinstaller_paths(path_value: str) -> str:
    """
    Remove PyInstaller-related paths from a PATH-style environment variable.

    Parameters
    ----------
    path_value : str
        The original value of the path variable (colon or semicolon separated).

    Returns
    -------
    str
        The filtered path value with PyInstaller paths removed.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return path_value

    separator = os.pathsep
    paths = path_value.split(separator)

    # Filter out paths that are inside the PyInstaller bundle
    filtered_paths = [
        p for p in paths if not p.startswith(meipass) and "_internal" not in p and "dist/_internal" not in p
    ]

    return separator.join(filtered_paths)


def isolate_library_paths_for_subprocess() -> None:
    """
    Remove or filter PyInstaller-bundled library paths from the environment.

    This function should be called early in SAM CLI initialization when running
    from a PyInstaller bundle. It ensures that external processes (npm, node, pip, etc.)
    use system libraries instead of the bundled ones.

    This is safe to call because:
    1. Python and its C extensions are already loaded
    2. The bundled libraries have served their purpose for the main process
    3. External processes need system libraries for compatibility

    Note: This modifies os.environ directly, affecting all subprocess calls
    that inherit the environment.
    """
    if not is_pyinstaller_bundle():
        LOG.debug("Not running from PyInstaller bundle, skipping library path isolation")
        return

    _save_original_library_paths()

    pyinstaller_path = get_pyinstaller_lib_path()
    LOG.debug("Running from PyInstaller bundle at: %s", getattr(sys, "_MEIPASS", "unknown"))
    LOG.debug("PyInstaller internal lib path: %s", pyinstaller_path)

    for var in LIBRARY_PATH_VARS:
        if var in os.environ:
            original_value = os.environ[var]
            filtered_value = _filter_pyinstaller_paths(original_value)

            if filtered_value:
                os.environ[var] = filtered_value
                LOG.debug("Filtered %s: '%s' -> '%s'", var, original_value, filtered_value)
            else:
                del os.environ[var]
                LOG.debug("Removed %s (was: '%s')", var, original_value)


def get_clean_env_for_subprocess(additional_vars_to_remove: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Get a copy of the current environment with library paths cleaned for subprocess use.

    This is useful when you need to pass an explicit environment to subprocess calls
    rather than relying on inheritance from os.environ.

    Parameters
    ----------
    additional_vars_to_remove : Optional[List[str]]
        Additional environment variables to remove from the returned environment.

    Returns
    -------
    Dict[str, str]
        A copy of os.environ with library paths filtered/removed.
    """
    env = os.environ.copy()

    if is_pyinstaller_bundle():
        for var in LIBRARY_PATH_VARS:
            if var in env:
                filtered = _filter_pyinstaller_paths(env[var])
                if filtered:
                    env[var] = filtered
                else:
                    del env[var]

    if additional_vars_to_remove:
        for var in additional_vars_to_remove:
            env.pop(var, None)

    return env


def get_original_library_paths() -> Dict[str, str]:
    """
    Get the original library path values before isolation was applied.

    This can be useful for debugging or if restoration is ever needed.

    Returns
    -------
    Dict[str, str]
        Dictionary of original library path environment variables.
    """
    original = _library_path_state["original_library_paths"]
    return dict(original) if original else {}
