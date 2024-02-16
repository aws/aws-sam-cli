"""
This class acts like a wrapper around output streams to provide any flexibility with output we need
"""

from io import BytesIO, TextIOWrapper
from typing import Optional, TextIO, Union


class StreamWriter:
    def __init__(self, stream: TextIO, stream_bytes: Optional[Union[TextIO, BytesIO]] = None, auto_flush: bool = False):
        """
        Instatiates new StreamWriter to the specified stream

        Parameters
        ----------
        stream io.RawIOBase
            Stream to wrap
        stream_bytes io.TextIO | io.BytesIO
            Stream to wrap if bytes are being written
        auto_flush bool
            Whether to autoflush the stream upon writing
        """
        self._stream = stream
        self._stream_bytes = stream if isinstance(stream, TextIOWrapper) else stream_bytes
        self._auto_flush = auto_flush

    @property
    def stream(self) -> TextIO:
        return self._stream

    def write_bytes(self, output: bytes):
        """
        Writes specified text to the underlying stream
        Parameters
        ----------
        output bytes-like object
            Bytes to write into buffer
        """
        # all these ifs are to satisfy the linting/type checking
        if not self._stream_bytes:
            return
        if isinstance(self._stream_bytes, TextIOWrapper):
            self._stream_bytes.buffer.write(output)
            if self._auto_flush:
                self._stream_bytes.flush()

        elif isinstance(self._stream_bytes, BytesIO):
            self._stream_bytes.write(output)
            if self._auto_flush:
                self._stream_bytes.flush()

    def write_str(self, output: str):
        """
        Writes specified text to the underlying stream

        Parameters
        ----------
        output string object
            String to write
        """
        self._stream.write(output)

        if self._auto_flush:
            self._stream.flush()

    def flush(self):
        self._stream.flush()
        if self._stream_bytes:
            self._stream_bytes.flush()
