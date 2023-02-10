import typing

from click import HelpFormatter
from click import style


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


class DefinitionRow(typing.NamedTuple):
    name: str
    help_text: str
    new: bool = False


class RootCommandHelpTextFormatter(HelpFormatter):

    # Picked an additive constant that gives an aesthetically pleasing look.
    # TODO(sriram-mv): Refactor to take terminal width into account.
    ADDITIVE_LEFT_JUSTIFICATION = 10
    LEFT_JUSTIFICATION_LENGTH = (
        max([len(command) for command in _SAM_CLI_COMMAND_SHORT_FORM]) + ADDITIVE_LEFT_JUSTIFICATION
    )
    NEW_TEXT = "*NEW*"
    NEW_COLOR = "bright_yellow"

    def write_dl(
        self,
        rows: typing.Sequence[DefinitionRow],
        new: bool = False,
        col_max: int = 30,
        col_spacing: int = 2,
    ) -> None:
        # Customize the logic to write to be based on justification rules and if a given row is to be highlighted.
        modified_rows = []
        for row in rows:
            modified_row = (row.name.ljust(self.LEFT_JUSTIFICATION_LENGTH), row.help_text.strip())
            if row.new:
                modified_row = (
                    style(
                        f"{row.name + ' ' + self.NEW_TEXT}".ljust(self.LEFT_JUSTIFICATION_LENGTH),
                        bold=True,
                        fg=self.NEW_COLOR,
                    ),
                    row.help_text.strip(),
                )
            modified_rows.append(modified_row)

        return super(RootCommandHelpTextFormatter, self).write_dl(modified_rows)

    def section(self, name: str, new_lines: int = 1) -> typing.Iterator[None]:
        # Customize section to start with a new line(s) and bold text.
        for _ in range(new_lines):
            self.write("\n")
        sections = super(RootCommandHelpTextFormatter, self).section(style(name, bold=True))
        return sections
