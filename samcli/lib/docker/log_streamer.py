"""
Log streaming utilities when streaming logs from Docker
"""
import os

from samcli.lib.package.stream_cursor_utils import cursor_up, cursor_left, cursor_down, clear_line


class LogStreamer:
    def __init__(self, stream, error_class, error_msg_prefix=""):
        self.stream = stream
        self.error_class = error_class
        self.error_msg_prefix = error_msg_prefix

    def stream_progress(self, logs):
        """
        Stream progress from docker push logs and move the cursor based on the log id.
        :param logs: generator from docker_clent.api.push
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
                    self.stream.write((cursor_up(change_cursor_count) + cursor_left).encode())
                except KeyError:
                    ids[_id] = len(ids)
            else:
                ids = dict()

            self._stream_write(_id, status, stream, progress, error, self.error_class)

            if _id:
                self.stream.write((cursor_down(change_cursor_count) + cursor_left).encode())
        self.stream.write(os.linesep.encode())

    def _stream_write(self, _id, status, stream, progress, error, error_class):
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
            raise error_class(msg=self.error_msg_prefix if self.error_msg_prefix + error else error)
        if not status and not stream:
            return

        # NOTE(sriram-mv): Required for the purposes of when the cursor overflows existing terminal buffer.
        if not stream:
            self.stream.write(os.linesep.encode())
            self.stream.write((cursor_up() + cursor_left).encode())
            self.stream.write(clear_line().encode())

        if not _id:
            self.stream.write(f"{stream}".encode())
            self.stream.write(f"{status}".encode())
        else:
            self.stream.write(f"\r{_id}: {status} {progress}".encode())
