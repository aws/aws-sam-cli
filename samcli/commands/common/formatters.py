"""
Shared formatter for all SAM CLI commands.
"""

from samcli.cli.formatters import RootCommandHelpTextFormatter
from samcli.cli.row_modifiers import BaseLineRowModifier


class CommandHelpTextFormatter(RootCommandHelpTextFormatter):
    """
    Shared formatter for command help text with configurable justification.
    """

    DEFAULT_ADDITIVE_JUSTIFICATION = 6

    def __init__(self, options, additive_justification=None, *args, **kwargs):
        """
        Initialize the formatter.

        Parameters
        ----------
        options : List[str]
            List of option names for calculating justification length
        additive_justification : int, optional
            Override the default additive justification value.
            If not provided, uses DEFAULT_ADDITIVE_JUSTIFICATION (6).
        """
        super().__init__(*args, **kwargs)
        justification = (
            additive_justification if additive_justification is not None else self.DEFAULT_ADDITIVE_JUSTIFICATION
        )
        max_option_length = max([len(option) for option in options]) if options else 0
        self.left_justification_length = min(
            max_option_length + justification,
            self.width // 2 - self.indent_increment,
        )
        self.modifiers = [BaseLineRowModifier()]
