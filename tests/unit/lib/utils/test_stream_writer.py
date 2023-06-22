"""
Tests for StreamWriter
"""

from unittest import TestCase

from samcli.lib.utils.stream_writer import StreamWriter

from unittest.mock import Mock


class TestStreamWriter(TestCase):
    def test_must_write_to_stream(self):
        buffer = "something"
        stream_mock = Mock()

        writer = StreamWriter(stream_mock)
        writer.write(buffer)

        stream_mock.write.assert_called_once_with(buffer)

    def test_must_flush_underlying_stream(self):
        stream_mock = Mock()
        writer = StreamWriter(stream_mock)

        writer.flush()

        stream_mock.flush.assert_called_once_with()

    def test_auto_flush_must_be_off_by_default(self):
        stream_mock = Mock()

        writer = StreamWriter(stream_mock)
        writer.write("something")

        stream_mock.flush.assert_not_called()

    def test_when_auto_flush_on_flush_after_each_write(self):
        stream_mock = Mock()
        flush_mock = Mock()

        stream_mock.flush = flush_mock

        lines = ["first", "second", "third"]

        writer = StreamWriter(stream_mock, True)

        for line in lines:
            writer.write(line)
            flush_mock.assert_called_once_with()
            flush_mock.reset_mock()
