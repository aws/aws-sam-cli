"""
Wrapper to generated colored messages for printing in Terminal
"""

import logging
import os
import platform
from enum import Enum

import click
from rich.logging import RichHandler
from rich.style import Style
from rich.text import Text

from samcli.lib.utils.sam_logging import SAM_CLI_LOGGER_NAME

# Enables ANSI escape codes on Windows
if platform.system().lower() == "windows":
    try:
        os.system("color")
    except Exception:
        pass


# Python 3.11 has StrEnum
class Colors(str, Enum):
    SUCCESS = "green"
    FAILURE = "red"
    WARNING = "yellow"
    PROGRESS = "cyan"


class Colored:
    """
    Helper class to add ANSI colors and decorations to text. Given a string, ANSI colors are added with special prefix
    and suffix characters that are specially interpreted by Terminals to display colors.

        Ex: "message" -> add red color -> \x1b[31mmessage\x1b[0m

    This class serves two purposes:
        - Hide the underlying library used to provide colors: In this case, we use ``click`` library which is usually
            used to build a CLI interface. We use ``click`` just to minimize the number of dependencies we add to this
            project. This class allows us to replace click with any other color library like ``pygments`` without
            changing callers.

        - Transparently turn off colors: In cases when the string is not written to Terminal (ex: log file) the ANSI
            color codes should not be written. This class supports the scenario by allowing you to turn off colors.
            Calls to methods like `red()` will simply return the input string.
    """

    def __init__(self, colorize=True):
        """
        Initialize the object

        Parameters
        ----------
        colorize : bool
            Optional. Set this to True to turn on coloring. False will turn off coloring
        """
        self.rich_logging = any(
            isinstance(handler, RichHandler) for handler in logging.getLogger(SAM_CLI_LOGGER_NAME).handlers
        )
        self.colorize = colorize

    def red(self, msg):
        """Color the input red"""
        return self._color(msg, "red")

    def green(self, msg):
        """Color the input green"""
        return self._color(msg, "green")

    def cyan(self, msg):
        """Color the input cyan"""
        return self._color(msg, "cyan")

    def white(self, msg):
        """Color the input white"""
        return self._color(msg, "white")

    def yellow(self, msg):
        """Color the input yellow"""
        return self._color(msg, "yellow")

    def underline(self, msg):
        """Underline the input"""
        return click.style(msg, underline=True) if self.colorize else msg

    def underline_log(self, msg):
        """Underline the input such that underlying Rich Logger understands it (if configured)."""
        if self.rich_logging:
            _color_msg = Text(msg, style=Style(underline=True))
            return _color_msg.markup if self.colorize else msg
        else:
            return click.style(msg, underline=True) if self.colorize else msg

    def bold(self, msg):
        """Bold the input"""
        return click.style(msg, bold=True) if self.colorize else msg

    def _color(self, msg, color):
        """Internal helper method to add colors to input"""
        kwargs = {"fg": color}
        return click.style(msg, **kwargs) if self.colorize else msg

    def _color_log(self, msg, color):
        """Marked up text with color used for logging with a logger"""
        _color_msg = Text(msg, style=Style(color=color))
        return _color_msg.markup if self.colorize else msg

    def color_log(self, msg, color):
        """Internal helper method to add colors such that underlying Rich Logger understands it (if configured)."""
        return self._color_log(msg=msg, color=color) if self.rich_logging else self._color(msg=msg, color=color)
