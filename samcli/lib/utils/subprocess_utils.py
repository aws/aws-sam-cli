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
from typing import Any, AnyStr, Callable, Dict, Optional, Union

from samcli.commands.exceptions import UserException
from samcli.lib.utils.stream_writer import StreamWriter

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
