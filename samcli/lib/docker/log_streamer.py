"""
Log streaming utilities when streaming logs from Docker
"""
import os

import docker
from docker.errors import APIError

from samcli.lib.package.stream_cursor_utils import cursor_up, cursor_left, cursor_down, clear_line
from samcli.lib.utils.stream_writer import StreamWriter


class LogStreamer:
    UP = "UP"
    DOWN = "DOWN"
    CLEAR = "CLEAR"

    def __init__(self, stream: StreamWriter, error_class: APIError.__class__, error_msg_prefix=""):
        self._stream = stream
        self._error_class = error_class
        self._error_msg_prefix = error_msg_prefix
        self._cursor_map = {
            self.UP: lambda cursor_count: cursor_up(cursor_count) + cursor_left,
            self.DOWN: lambda cursor_count: cursor_down(cursor_count) + cursor_left,
            self.CLEAR: lambda cursor_count: clear_line(cursor_count),
        }

    def cursor_format(self, cursor_direction: str, count: int = 1):
        """
        Cursor manipulation function depending on cursor direction.
        :param cursor_direction: supported directions are UP, DOWN and CLEAR.
        :param count: cursor function to be applied for 'count' lines.
        :return: cursor manipulation function
        """
        return self._cursor_map[cursor_direction](count)

    def stream_progress(self, logs: docker.APIClient.logs):
        """
        Stream progress from docker push logs and move the cursor based on the log id.
        :param logs: generator from docker_clent.APIClient.logs
        """
        ids = dict()
        for log in logs:
            _id = log.get("id", "")
            status = log.get("status", "")
            stream = log.get("stream", "")
            progress = log.get("progress", "")
            error = log.get("error", "")
            change_cursor_count = 0
            if _id:
                try:
                    curr_log_line_id = ids[_id]
                    change_cursor_count = len(ids) - curr_log_line_id
                    self._stream.write(self.cursor_format(LogStreamer.UP, change_cursor_count), encode=True)
                except KeyError:
                    ids[_id] = len(ids)
            else:
                ids = dict()

            self._stream_write(_id, status, stream, progress, error, self._error_class)

            if _id:
                self._stream.write(self.cursor_format(LogStreamer.DOWN, change_cursor_count), encode=True)
        self._stream.write(os.linesep, encode=True)

    def _stream_write(
        self, _id: str, status: str, stream: bytes, progress: str, error: str, error_class: APIError.__class__
    ):
        """
        Write stream information to stderr, if the stream information contains a log id,
        use the carriage return character to rewrite that particular line.
        :param _id: docker log id
        :param status: docker log status
        :param stream: stream, usually stderr
        :param progress: docker log progress
        :param error: docker log error
        :param error_class: Exception class to raise
        """
        if error:
            raise error_class(msg=self._error_msg_prefix if self._error_msg_prefix + error else error)
        if not status and not stream:
            return

        # NOTE(sriram-mv): Required for the purposes of when the cursor overflows existing terminal buffer.
        if not stream:
            self._stream.write(os.linesep, encode=True)
            self._stream.write(self.cursor_format(LogStreamer.UP), encode=True)
            self._stream.write(self.cursor_format(LogStreamer.CLEAR), encode=True)

        if not _id:
            self._stream.write(f"{stream}", encode=True)
            self._stream.write(f"{status}", encode=True)
        else:
            self._stream.write(f"\r{_id}: {status} {progress}", encode=True)
