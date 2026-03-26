"""
Shared formatter for all SAM CLI commands.
"""

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import BaseLineRowModifier


class CommandHelpTextFormatter(RootCommandHelpTextFormatter):
    """
    Shared formatter for command help text.
    """

    ADDITIVE_JUSTIFICATION = 17

    def __init__(self, options, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.left_justification_length = min(
            max([len(option) for option in options]) + self.ADDITIVE_JUSTIFICATION,
            self.width // 2 - self.indent_increment,
        )
        self.modifiers = [BaseLineRowModifier()]
