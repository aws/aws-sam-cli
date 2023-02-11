from typing import NamedTuple, Sequence, Iterator, Optional

from click import style, HelpFormatter


_SAM_CLI_COMMAND_SHORT_FORM = [
    "init",
    "validate",
    "build",
    "local",
    "package",
    "deploy",
    "delete",
    "logs",
    "publish",
    "traces",
    "sync",
    "pipeline",
    "list",
]


class DefinitionRow(NamedTuple):
    name: str
    help_text: str
    new: bool = False


class RootCommandHelpTextFormatter(HelpFormatter):

    NEW_TEXT = "~NEW!~"
    NEW_COLOR = "bright_yellow"
    # Picked an additive constant that gives an aesthetically pleasing look.
    ADDITIVE_JUSTIFICATION = 10

    def __init__(self, *args, **kwargs):
        super(RootCommandHelpTextFormatter, self).__init__(*args, **kwargs)
        # NOTE(sriram-mv): Do not left justify for more than half the width.
        self.left_justification_length = min(
            max([len(command) for command in _SAM_CLI_COMMAND_SHORT_FORM]) + self.ADDITIVE_JUSTIFICATION,
            self.width // 2 - self.indent_increment,
        )

    def write_usage(self, prog: str, args: str = "", prefix: Optional[str] = None) -> None:
        super(RootCommandHelpTextFormatter, self).write_usage(prog=style(prog, bold=True), args=args, prefix=prefix)

    def write_heading(self, heading: str) -> None:
        super(RootCommandHelpTextFormatter, self).write_heading(style(heading, bold=True))

    def write_dl(
        self,
        rows: Sequence[DefinitionRow],
        new: bool = False,
        col_max: int = 30,
        col_spacing: int = 2,
        new_lines: int = 0,
    ) -> None:
        for _ in range(new_lines):
            self.write("\n")
        # Customize the logic to write to be based on justification rules and if a given row is to be highlighted.
        modified_rows = []
        for row in rows:
            modified_row = (row.name.ljust(self.left_justification_length), row.help_text.strip())
            if row.new:
                modified_row = (
                    style(
                        f"{row.name + ' ' + self.NEW_TEXT}".ljust(self.left_justification_length),
                        bold=True,
                        fg=self.NEW_COLOR,
                    ),
                    row.help_text.strip(),
                )
            modified_rows.append(modified_row)

        return super(RootCommandHelpTextFormatter, self).write_dl(modified_rows)

    def section(self, name: str = "", underline: bool = True, new_lines: int = 0) -> Iterator[None]:
        # Customize section to start with a new line(s) and bold text.
        for _ in range(new_lines):
            self.write("\n")
        sections = super(RootCommandHelpTextFormatter, self).section(style(name, bold=True, underline=underline))
        return sections
