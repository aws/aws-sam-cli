"""
This class acts like a wrapper around output streams to provide any flexibility with output we need
"""
from typing import TextIO, Union


class StreamWriter:
    def __init__(self, stream: TextIO, auto_flush: bool = False):
        """
        Instatiates new StreamWriter to the specified stream

        Parameters
        ----------
        stream io.RawIOBase
            Stream to wrap
        auto_flush bool
            Whether to autoflush the stream upon writing
        """
        self._stream = stream
        self._auto_flush = auto_flush

    @property
    def stream(self) -> TextIO:
        return self._stream

    def write_bytes(self, output: Union[bytes, bytearray]):
        """
        Writes specified text to the underlying stream

        Parameters
        ----------
        output bytes-like object
            Bytes to write into buffer
        """
        self._stream.buffer.write(output)

        if self._auto_flush:
            self._stream.flush()

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
