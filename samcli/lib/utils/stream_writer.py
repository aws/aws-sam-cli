"""
This class acts like a wrapper around output streams to provide any flexibility with output we need
"""
import io
import json
from json import JSONDecodeError

from click.termui import style


class StreamWriter:

    COLORS = {
        'GENERIC_JSON': {'fg': 'green', 'bold': True},
        'DEBUG': {'fg': 'blue', 'bold': True},
        'INFO': {'fg': 'cyan', 'bold': True},
        'WARNING': {'fg': 'yellow', 'bold': True},
        'ERROR': {'fg': 'red', 'bold': True},
        'CRITICAL': {'fg': 'white', 'bg': 'red', 'bold': True},
    }

    def __init__(self, stream, auto_flush=False, pretty_json=False):
        """
        Instatiates new StreamWriter to the specified stream

        Parameters
        ----------
        stream io.RawIOBase
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
    def stream(self):
        return self._stream

    def write(self, output, encode=False):
        """
        Writes specified text to the underlying stream

        Parameters
        ----------
        output bytes-like object
            Bytes to write
        """
        if encode:
            output = output.encode()

        if self._pretty_json:
            try:
                self._buffer.write(output.encode())
            except AttributeError:
                self._stream_supports_bytes = True
                self._buffer.write(output)
            self.write_from_buffer()
        else:
            self._stream.write(output)

    def flush(self):
        if self._pretty_json:
            self.write_from_buffer(force_write=True)
        self._stream.flush()

    def write_from_buffer(self, encode=False, force_write=False):
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

    def format_line(self, line):
        try:
            line_obj = json.loads(line)
            line = json.dumps(line_obj, indent=4)
            if self._colorize:
                if 'exception' in line_obj and 'message' in line_obj:
                    style_args = StreamWriter.COLORS['CRITICAL']
                elif 'level' in line_obj:
                    style_args = StreamWriter.COLORS.get(line_obj['level'], StreamWriter.COLORS['GENERIC_JSON'])
                else:
                    style_args = StreamWriter.COLORS['GENERIC_JSON']

                line = style(line, **style_args)
            line = line.encode()
        except JSONDecodeError:
            pass
        return line
