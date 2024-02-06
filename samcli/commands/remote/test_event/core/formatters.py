"""
Remote Test Event Command Formatter base.
"""

from typing import List

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import BaseLineRowModifier


class RemoteTestEventCommandHelpTextFormatter(RootCommandHelpTextFormatter):
    ADDITIVE_JUSTIFICATION = 17
    ALL_OPTIONS: List[str] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # NOTE: Add Additional space after determining the longest option.
        # However, do not justify with padding for more than half the width of
        # the terminal to retain aesthetics.
        self.left_justification_length = min(
            max([len(option) for option in self.ALL_OPTIONS]) + self.ADDITIVE_JUSTIFICATION,
            self.width // 2 - self.indent_increment,
        )
        self.modifiers = [BaseLineRowModifier()]
