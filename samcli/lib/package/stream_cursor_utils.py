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


def cursor_up(count=1):
    return ESC + str(count) + "A"


def cursor_down(count=1):
    return ESC + str(count) + "B"


def clear_line():
    return ESC + "0K"


cursor_left = ESC + "G"
