"""
This class acts like a wrapper around output streams to provide any flexibility with output we need
"""


class StreamWriter:
    def __init__(self, stream, auto_flush=False):
        """Instatiates new StreamWriter to the specified stream"""
        self._stream = stream
        self._auto_flush = auto_flush

    def write(self, output):
        """Writes specified text to the underlying stream

        Parameters
        ----------
        output :


        Returns
        -------


        """
        self._stream.write(output)

        if self._auto_flush:
            self._stream.flush()

    def flush(self):
        self._stream.flush()
