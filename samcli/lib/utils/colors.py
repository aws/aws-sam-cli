"""
Wrapper to generated colored messages for printing in Terminal
"""

import platform
import os

import click

# Enables ANSI escape codes on Windows
if platform.system().lower() == "windows":
    try:
        os.system("color")
    except Exception:
        pass


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

    def __init__(self, colorize=True):  # type: ignore[no-untyped-def]
        """
        Initialize the object

        Parameters
        ----------
        colorize : bool
            Optional. Set this to True to turn on coloring. False will turn off coloring
        """
        self.colorize = colorize

    def red(self, msg):  # type: ignore[no-untyped-def]
        """Color the input red"""
        return self._color(msg, "red")  # type: ignore[no-untyped-call]

    def green(self, msg):  # type: ignore[no-untyped-def]
        """Color the input green"""
        return self._color(msg, "green")  # type: ignore[no-untyped-call]

    def cyan(self, msg):  # type: ignore[no-untyped-def]
        """Color the input cyan"""
        return self._color(msg, "cyan")  # type: ignore[no-untyped-call]

    def white(self, msg):  # type: ignore[no-untyped-def]
        """Color the input white"""
        return self._color(msg, "white")  # type: ignore[no-untyped-call]

    def yellow(self, msg):  # type: ignore[no-untyped-def]
        """Color the input yellow"""
        return self._color(msg, "yellow")  # type: ignore[no-untyped-call]

    def underline(self, msg):  # type: ignore[no-untyped-def]
        """Underline the input"""
        return click.style(msg, underline=True) if self.colorize else msg

    def bold(self, msg):  # type: ignore[no-untyped-def]
        """Bold the input"""
        return click.style(msg, bold=True) if self.colorize else msg

    def _color(self, msg, color):  # type: ignore[no-untyped-def]
        """Internal helper method to add colors to input"""
        kwargs = {"fg": color}
        return click.style(msg, **kwargs) if self.colorize else msg
