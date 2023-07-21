"""
Utils for invoking subprocess calls
"""
import logging
import os
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from subprocess import PIPE, Popen
from time import sleep
from typing import IO, Any, AnyStr, Callable, Dict, Optional, Union

from samcli.commands.exceptions import UserException
from samcli.lib.utils.stream_writer import StreamWriter

LOG = logging.getLogger(__name__)


class LoadingPatternError(UserException):
    def __init__(self, ex):
        self.ex = ex
        message_fmt = f"Failed to execute the subprocess. {ex}"
        super().__init__(message=message_fmt.format(ex=self.ex))


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
    stream_writer.write(".")
    stream_writer.flush()
    sleep(loading_pattern_rate)


def invoke_subprocess_with_loading_pattern(
    command_args: Dict[str, Any],
    loading_pattern: Callable[[StreamWriter], None] = default_loading_pattern,
    stream_writer: Optional[StreamWriter] = None,
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

    Returns
    -------
    str
        A string containing the process output
    """
    stream_writer = stream_writer or StreamWriter(sys.stderr)
    process_output = ""

    if not command_args.get("stdout"):
        # Default stdout to PIPE if not specified so
        # that output isn't printed along with dots
        command_args["stdout"] = PIPE

    try:
        keep_printing = LOG.getEffectiveLevel() >= logging.INFO

        def _print_loading_pattern():
            while keep_printing:
                loading_pattern(stream_writer)

        # Popen is async as opposed to run so we can print while we wait
        with Popen(**command_args) as process:
            with ThreadPoolExecutor() as executor:
                executor.submit(_print_loading_pattern)

                if process.stdout:
                    # Logging level is DEBUG, streaming logs instead
                    # we read from subprocess stdout to avoid the deadlock process.wait function
                    # for more detail check this python bug https://bugs.python.org/issue1256
                    for line in process.stdout:
                        decoded_line = _check_and_process_bytes(line)
                        if LOG.getEffectiveLevel() < logging.INFO:
                            LOG.debug(decoded_line)
                        process_output += decoded_line

                return_code = process.wait()
                keep_printing = False

                stream_writer.write(os.linesep)
                stream_writer.flush()
                process_stderr = _check_and_convert_stream_to_string(process.stderr)

                if return_code:
                    raise LoadingPatternError(
                        f"The process {command_args.get('args', [])} returned a "
                        f"non-zero exit code {process.returncode}. {process_stderr}"
                    )

    except (OSError, ValueError) as e:
        raise LoadingPatternError(f"Subprocess execution failed {command_args.get('args', [])}. {e}") from e

    return process_output


def _check_and_convert_stream_to_string(stream: Optional[IO[AnyStr]]) -> str:
    stream_as_str = ""
    if stream:
        byte_stream = stream.read()
        stream_as_str = _check_and_process_bytes(byte_stream)
    return stream_as_str


def _check_and_process_bytes(check_value: AnyStr) -> str:
    if isinstance(check_value, bytes):
        return check_value.decode("utf-8").strip()
    return check_value
