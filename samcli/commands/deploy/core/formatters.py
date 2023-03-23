from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.deploy.core.options import ALL_OPTIONS


class DeployCommandHelpTextFormatter(RootCommandHelpTextFormatter):
    # Picked an additive constant that gives an aesthetically pleasing look.
    ADDITIVE_JUSTIFICATION = 15

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Additional space after determining the longest option.
        # However, do not justify with padding for more than half the width of
        # the terminal to retain aesthetics.
        self.left_justification_length = min(
            max([len(option) for option in ALL_OPTIONS]) + self.ADDITIVE_JUSTIFICATION,
            self.width // 2 - self.indent_increment,
        )
        self.modifiers = [BaseLineRowModifier()]
