"""
This class acts like a wrapper around output streams to provide any flexibility with output we need
"""


class StreamWriter:
    def __init__(self, stream, auto_flush=False):
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
        self._stream.write(output.encode() if encode else output)

        if self._auto_flush:
            self._stream.flush()

    def flush(self):
        self._stream.flush()
