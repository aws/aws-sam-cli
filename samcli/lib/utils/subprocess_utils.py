"""
Utils for invoking subprocess calls
"""
from time import sleep

import sys
from subprocess import Popen

from typing import Callable, Dict, Any, Optional, Union

from samcli.commands.exceptions import UserException
from samcli.lib.utils.stream_writer import StreamWriter


class LoadingPatternError(UserException):
    def __init__(self, ex):
        self.ex = ex
        message_fmt = f"Failed to execute the subprocess. {ex}"
        super().__init__(message=message_fmt.format(ex=self.ex))


def _default_loading_pattern(stream_writer: Optional[StreamWriter] = None) -> None:
    """
    A loading pattern that just prints '.' to the terminal

    Parameters
    ----------
    stream_writer: Optional[StreamWriter]
        The stream to which to write the pattern
    """
    stream_writer = stream_writer or StreamWriter(sys.stderr)
    stream_writer.write(".")
    stream_writer.flush()


def invoke_subprocess_with_loading_pattern(
    command_args: Dict[str, Any],
    loading_pattern_rate: float = 0.5,
    loading_pattern: Callable[[StreamWriter], None] = _default_loading_pattern,
    stream_writer: Optional[StreamWriter] = None,
) -> Optional[Union[str, bytes]]:
    """
    Wrapper for Popen to asynchronously invoke a subprocess while
    printing a given pattern until the subprocess is complete

    Parameters
    ----------
    command_args: Dict[str, Any]
        The arguments to give to the Popen call, should contain at least one parameter "args"
    loading_pattern_rate: int
        How frequently to generate the pattern
    loading_pattern: Callable[[StreamWriter], None]
        A function generating a pattern to the given stream
    stream_writer: Optional[StreamWriter]
        The stream to which to write the pattern

    Returns
    -------
    Optional[Union[str, bytes]]
        A string containing the process output
    """
    stream_writer = stream_writer or StreamWriter(sys.stderr)
    process_output = None
    try:
        # Popen is async as opposed to run so we can print while we wait
        with Popen(**command_args) as process:
            # process.poll() returns None until the process exits
            while process.poll() is None:
                loading_pattern(stream_writer)
                sleep(loading_pattern_rate)

            stream_writer.write("\n")
            stream_writer.flush()

            if process.stdout:
                process_output = process.stdout.read()

            process_stderr = None
            if process.stderr:
                process_stderr = process.stderr.read()

            if process.returncode:
                raise LoadingPatternError(
                    f"The process {command_args.get('args', [])} returned a "
                    f"non-zero exit code {process.returncode}. {process_stderr}"
                )

    except (OSError, ValueError) as e:
        raise LoadingPatternError(f"Subprocess execution failed {command_args.get('args', [])}. {e}") from e

    return process_output
