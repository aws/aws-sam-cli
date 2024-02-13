"""
Remote Invoke Command Formatter.
"""

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.remote.invoke.core.options import ALL_OPTIONS


class RemoteInvokeCommandHelpTextFormatter(RootCommandHelpTextFormatter):
    ADDITIVE_JUSTIFICATION = 17

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # NOTE: Add Additional space after determining the longest option.
        # However, do not justify with padding for more than half the width of
        # the terminal to retain aesthetics.
        self.left_justification_length = min(
            max([len(option) for option in ALL_OPTIONS]) + self.ADDITIVE_JUSTIFICATION,
            self.width // 2 - self.indent_increment,
        )
        self.modifiers = [BaseLineRowModifier()]
