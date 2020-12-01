from unittest import TestCase

from samcli.lib.package.stream_cursor_utils import cursor_up, cursor_down, cursor_left, clear_line


class TestStreamCursorUtils(TestCase):
    def test_cursor_utils(self):
        self.assertEqual(cursor_up(count=1), "\x1b[1A")
        self.assertEqual(cursor_down(count=1), "\x1b[1B")
        self.assertEqual(cursor_left, "\x1b[G")
        self.assertEqual(clear_line(), "\x1b[0K")
