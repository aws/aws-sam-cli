from unittest import TestCase
from parameterized import parameterized, param

from samcli.lib.utils.colors import Colored


class TestColored(TestCase):
    def setUp(self):
        self.msg = "message"

    @parameterized.expand(
        [
            param("red", "\x1b[31m"),
            param("green", "\x1b[32m"),
            param("cyan", "\x1b[36m"),
            param("white", "\x1b[37m"),
            param("yellow", "\x1b[33m"),
            param("underline", "\x1b[4m"),
        ]
    )
    def test_various_decorations(self, decoration_name, ansi_prefix):
        expected = ansi_prefix + self.msg + "\x1b[0m"

        with_color = Colored()
        without_color = Colored(colorize=False)

        self.assertEqual(expected, getattr(with_color, decoration_name)(self.msg))
        self.assertEqual(self.msg, getattr(without_color, decoration_name)(self.msg))
