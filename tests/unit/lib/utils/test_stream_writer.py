"""
Tests for StreamWriter
"""

from io import BytesIO, TextIOWrapper
from unittest import TestCase

from samcli.lib.utils.stream_writer import StreamWriter

from unittest.mock import Mock


class TestStreamWriter(TestCase):
    def test_must_write_to_stream(self):
        buffer = b"something"
        stream_mock = Mock()

        writer = StreamWriter(stream_mock)
        writer.write_str(buffer.decode("utf-8"))

        stream_mock.write.assert_called_once_with(buffer.decode("utf-8"))

    def test_must_write_to_stream_bytes(self):
        img_bytes = b"\xff\xab\x11"
        stream_mock = Mock()
        byte_stream_mock = Mock(spec=BytesIO)

        writer = StreamWriter(stream_mock, byte_stream_mock)
        writer.write_bytes(img_bytes)

        byte_stream_mock.write.assert_called_once_with(img_bytes)

    def test_must_write_to_stream_bytes_for_stdout(self):
        img_bytes = b"\xff\xab\x11"
        stream_mock = Mock()
        byte_stream_mock = Mock(spec=TextIOWrapper)

        writer = StreamWriter(stream_mock, byte_stream_mock)
        writer.write_bytes(img_bytes)

        byte_stream_mock.buffer.write.assert_called_once_with(img_bytes)

    def test_must_not_write_to_stream_bytes_if_not_defined(self):
        img_bytes = b"\xff\xab\x11"
        stream_mock = Mock()

        writer = StreamWriter(stream_mock)
        writer.write_bytes(img_bytes)

        stream_mock.write.assert_not_called()

    def test_must_flush_underlying_stream(self):
        stream_mock = Mock()
        writer = StreamWriter(stream_mock)

        writer.flush()

        stream_mock.flush.assert_called_once_with()

    def test_auto_flush_must_be_off_by_default(self):
        stream_mock = Mock()

        writer = StreamWriter(stream_mock)
        writer.write_str("something")

        stream_mock.flush.assert_not_called()

    def test_when_auto_flush_on_flush_after_each_write(self):
        stream_mock = Mock()
        flush_mock = Mock()

        stream_mock.flush = flush_mock

        lines = ["first", "second", "third"]

        writer = StreamWriter(stream_mock, auto_flush=True)

        for line in lines:
            writer.write_str(line)
            flush_mock.assert_called_once_with()
            flush_mock.reset_mock()
