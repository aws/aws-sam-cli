"""
Invoke API Command Formatter.
"""
from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.local.start_api.core.options import ALL_OPTIONS


class InvokeStartAPICommandHelpTextFormatter(RootCommandHelpTextFormatter):
    ADDITIVE_JUSTIFICATION = 6

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # NOTE(sriram-mv): Add Additional space after determining the longest option.
        # However, do not justify with padding for more than half the width of
        # the terminal to retain aesthetics.
        self.left_justification_length = min(
            max([len(option) for option in ALL_OPTIONS]) + self.ADDITIVE_JUSTIFICATION,
            self.width // 2 - self.indent_increment,
        )
        self.modifiers = [BaseLineRowModifier()]
