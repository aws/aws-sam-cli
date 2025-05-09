"""
Log streaming utilities when streaming logs from Docker
"""

import os
from typing import Dict

import docker

from samcli.lib.package.stream_cursor_utils import (
    ClearLineFormatter,
    CursorDownFormatter,
    CursorLeftFormatter,
    CursorUpFormatter,
)
from samcli.lib.utils.stream_writer import StreamWriter


class LogStreamError(Exception):
    def __init__(self, msg: str) -> None:
        Exception.__init__(self, msg)


class LogStreamer:
    def __init__(self, stream: StreamWriter, throw_on_error: bool = True):
        self._stream = stream
        self._cursor_up_formatter = CursorUpFormatter()
        self._cursor_down_formatter = CursorDownFormatter()
        self._cursor_left_formatter = CursorLeftFormatter()
        self._cursor_clear_formatter = ClearLineFormatter()
        self._throw_on_error = throw_on_error

    def stream_progress(self, logs: docker.APIClient.logs):
        """
        Stream progress from docker push logs and move the cursor based on the log id.
        :param logs: generator from docker_clent.APIClient.logs
        """
        ids: Dict[str, int] = dict()
        for log in logs:
            _id = log.get("id", "")
            status = log.get("status", "")
            stream = log.get("stream", "")
            progress = log.get("progress", "")
            error = log.get("error", "")
            change_cursor_count = 0
            if _id:
                if _id not in ids:
                    ids[_id] = len(ids)
                else:
                    curr_log_line_id = ids[_id]
                    change_cursor_count = len(ids) - curr_log_line_id
                    self._stream.write_str(
                        self._cursor_up_formatter.cursor_format(change_cursor_count)
                        + self._cursor_left_formatter.cursor_format()
                    )

            self._stream_write(_id, status, stream, progress, error)

            if _id:
                self._stream.write_str(
                    self._cursor_down_formatter.cursor_format(change_cursor_count)
                    + self._cursor_left_formatter.cursor_format()
                )
        self._stream.write_str(os.linesep)

    def _stream_write(self, _id: str, status: str, stream: str, progress: str, error: str):
        """
        Write stream information to stderr, if the stream information contains a log id,
        use the carriage return character to rewrite that particular line.
        :param _id: docker log id
        :param status: docker log status
        :param stream: stream, usually stderr
        :param progress: docker log progress
        :param error: docker log error
        """
        if error:
            if self._throw_on_error:
                raise LogStreamError(msg=error)
            else:
                self._stream.write_str(error)
                return

        if not status and not stream:
            return

        # NOTE(sriram-mv): Required for the purposes of when the cursor overflows existing terminal buffer.
        if not stream:
            self._stream.write_str(os.linesep)
            self._stream.write_str(
                self._cursor_up_formatter.cursor_format() + self._cursor_left_formatter.cursor_format()
            )
            self._stream.write_str(self._cursor_clear_formatter.cursor_format())

        if not _id:
            self._stream.write_str(stream)
            self._stream.write_str(status)
        else:
            self._stream.write_str(f"\r{_id}: {status} {progress}")
