"""
This class acts like a wrapper around output streams to provide any flexibility with output we need
"""
import io
import json
from json import JSONDecodeError
from typing import IO, Callable, Dict, Union

from click.termui import style


class StreamWriter:
    def __init__(self, stream: IO, auto_flush: bool = False, pretty_json: bool = False):
        """
        Instatiates new StreamWriter to the specified stream

        Parameters
        ----------
        stream IO
            Stream to wrap
        auto_flush bool
            Whether to autoflush the stream upon writing
        pretty_json bool
            Whether to autoformat and color lines containing valid JSON
        """
        self._stream = stream
        self._stream_supports_bytes = False
        self._auto_flush = auto_flush
        self._colorize = pretty_json and stream.isatty()
        self._pretty_json = pretty_json
        self._buffer = io.BytesIO()

    @property
    def stream(self) -> IO:
        return self._stream

    def write(self, output: Union[str, bytes], encode: bool = False) -> None:
        """
        Writes specified text to the underlying stream

        Parameters
        ----------
        output bytes-like object
            Bytes to write
        """
        if isinstance(output, str) and encode:
            output = output.encode()

        if self._pretty_json:
            if isinstance(output, bytes):
                self._stream_supports_bytes = True
            else:
                output = output.encode()
            self._buffer.write(output)
            self.write_from_buffer()
        else:
            self._stream.write(output)

    def flush(self) -> None:
        if self._pretty_json:
            self.write_from_buffer(force_write=True)
        self._stream.flush()

    def write_from_buffer(self, encode: bool = False, force_write: bool = False) -> None:
        remainder = b''
        self._buffer.seek(0)
        for line in self._buffer:
            if line[-1:] == b'\n':
                line = self.format_line(line.rstrip(b'\n')) + b'\n'
                self._stream.write(line if self._stream_supports_bytes else line.decode())
            elif force_write:
                line = self.format_line(line)
                self._stream.write(line if self._stream_supports_bytes else line.decode())
            else:
                remainder = line

        self._buffer.seek(0)
        self._buffer.truncate()
        self._buffer.write(remainder)

        if self._auto_flush:
            self._stream.flush()

    def format_line(self, line: bytes) -> bytes:
        try:
            line_obj = json.loads(line)
            line_str = json.dumps(line_obj, indent=4)
            if self._colorize:
                styles: Dict[str, Callable] = {
                    'GENERIC_JSON': lambda line_str: style(line_str, fg='green', bold=True),
                    'DEBUG': lambda line_str: style(line_str, fg='blue', bold=True),
                    'INFO': lambda line_str: style(line_str, fg='cyan', bold=True),
                    'WARNING': lambda line_str: style(line_str, fg='yellow', bold=True),
                    'ERROR': lambda line_str: style(line_str, fg='red', bold=True),
                    'CRITICAL': lambda line_str: style(line_str, fg='white', bg='red', bold=True),
                }

                if 'exception' in line_obj and 'message' in line_obj:
                    line_str = styles['CRITICAL'](line_str)
                elif 'level' in line_obj and line_obj['level'].upper() in styles.keys():
                    line_str = styles[line_obj['level'].upper()](line_str)
                else:
                    line_str = styles['GENERIC_JSON'](line_str)

            line = line_str.encode()
        except JSONDecodeError:
            pass
        return line
