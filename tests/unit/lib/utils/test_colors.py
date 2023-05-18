from logging import StreamHandler
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized, param
from rich.logging import RichHandler

from samcli.lib.utils.colors import Colored


class TestColored(TestCase):
    def setUp(self):
        self.msg = "message"
        self.color = "green"

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

    @parameterized.expand(
        [
            param([RichHandler()], "[green]message[/green]"),
            param([StreamHandler()], "\x1b[32mmessage\x1b[0m"),
        ]
    )
    @patch("samcli.lib.utils.colors.logging")
    def test_color_log_log_handlers(self, log_handler, response, mock_logger):
        mock_logger.getLogger().handlers = log_handler
        with_rich_color = Colored(colorize=True)
        self.assertEqual(with_rich_color.color_log(msg=self.msg, color=self.color), response)
