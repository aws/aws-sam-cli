"""
Click Help Formatter Classes that are customized for the root command.
"""

from contextlib import contextmanager
from typing import Iterator, Optional, Sequence

from click import HelpFormatter, style

from samcli.cli.root.command_list import SAM_CLI_COMMANDS
from samcli.cli.row_modifiers import BaseLineRowModifier, RowDefinition


class RootCommandHelpTextFormatter(HelpFormatter):
    # Picked an additive constant that gives an aesthetically pleasing look.
    ADDITIVE_JUSTIFICATION = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # NOTE(sriram-mv): Add Additional space after determining the longest command.
        # However, do not justify with padding for more than half the width of
        # the terminal to retain aesthetics
        self.left_justification_length = min(
            max([len(command) for command, _ in SAM_CLI_COMMANDS.items()]) + self.ADDITIVE_JUSTIFICATION,
            self.width // 2 - self.indent_increment,
        )
        self.modifiers = [BaseLineRowModifier()]

    def write_usage(self, prog: str, args: str = "", prefix: Optional[str] = None) -> None:
        super().write_usage(prog=style(prog, bold=True), args=args, prefix=prefix)

    def write_heading(self, heading: str) -> None:
        super().write_heading(style(heading, bold=True))

    def write_rd(
        self,
        rows: Sequence[RowDefinition],
        col_max: int = 30,
        col_spacing: int = 2,
    ) -> None:
        modified_rows = []
        for row in rows:
            extra_row_modifiers = row.extra_row_modifiers or []
            modified_row = row
            for row_modifier in self.modifiers + extra_row_modifiers:
                modified_row = row_modifier.apply(row=modified_row, justification_length=self.left_justification_length)
            modified_rows.append((modified_row.name, modified_row.text))

        super().write_dl(modified_rows, col_max=col_max, col_spacing=col_spacing)

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        with super().section(style(name, bold=True, underline=True)):
            try:
                yield
            finally:
                pass

    @contextmanager
    def indented_section(self, name: str, extra_indents: int = 0) -> Iterator[None]:
        with super().section(style(name, bold=True, underline=True)):
            for _ in range(extra_indents):
                self.indent()
            try:
                yield
            finally:
                for _ in range(extra_indents):
                    self.dedent()
