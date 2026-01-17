from unittest import TestCase

from samcli.lib.package.stream_cursor_utils import (
    CursorFormatter,
    CursorUpFormatter,
    CursorDownFormatter,
    CursorLeftFormatter,
    ClearLineFormatter,
)


class TestStreamCursorUtils(TestCase):
    def test_cursor_utils(self):
        self.assertEqual(CursorUpFormatter().cursor_format(count=1), "\x1b[1A")
        self.assertEqual(CursorDownFormatter().cursor_format(count=1), "\x1b[1B")
        self.assertEqual(CursorLeftFormatter().cursor_format(), "\x1b[0G")
        self.assertEqual(ClearLineFormatter().cursor_format(), "\x1b[0K")

    def test_base_formatter_is_noop(self):
        self.assertIsNone(CursorFormatter().cursor_format(count=0))
