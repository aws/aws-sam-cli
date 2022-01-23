"""
Stream cursor utilities for moving cursor in the terminal.
"""
import os
import platform

# NOTE: ANSI escape codes.
# NOTE: Still needs investigation on non terminal environments.
ESC = "\u001B["

# Enables ANSI escape codes on Windows
if platform.system().lower() == "windows":
    try:
        os.system("color")
    except Exception:
        pass


class CursorFormatter:
    """
    Base class for defining how cursor is to be manipulated.
    """

    def __init__(self):
        pass

    def cursor_format(self, count):
        pass


class CursorUpFormatter(CursorFormatter):
    """
    Class for formatting and outputting moving the cursor up within the stream of bytes.
    """

    def cursor_format(self, count=0):
        return ESC + str(count) + "A"


class CursorDownFormatter(CursorFormatter):
    """
    Class for formatting and outputting moving the cursor down within the stream of bytes.
    """

    def cursor_format(self, count=0):
        return ESC + str(count) + "B"


class ClearLineFormatter(CursorFormatter):
    """
    Class for formatting and outputting clearing the cursor within the stream of bytes.
    """

    def cursor_format(self, count=0):
        return ESC + str(count) + "K"


class CursorLeftFormatter(CursorFormatter):
    """
    Class for formatting and outputting moving the cursor left within the stream of bytes.
    """

    def cursor_format(self, count=0):
        return ESC + str(count) + "G"
