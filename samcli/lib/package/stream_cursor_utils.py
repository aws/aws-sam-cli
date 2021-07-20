"""
Stream cursor utilities for moving cursor in the terminal.
"""

# NOTE: ANSI escape codes.
# NOTE: Still needs investigation on non terminal environments.
ESC = "\u001B["


def cursor_up(count=1):
    return ESC + str(count) + "A"


def cursor_down(count=1):
    return ESC + str(count) + "B"


def clear_line():
    return ESC + "0K"


cursor_left = ESC + "G"
