"""
Row Definition and Row Modifiers to be used with `click.HelpFormatter write_dl methods`.
"""

from abc import ABC
from typing import List, NamedTuple

from click import style


class RowModifier(ABC):
    def apply(self, row, justification_length):
        raise NotImplementedError


class RowDefinition(NamedTuple):
    name: str = ""
    text: str = ""
    rank: int = 0
    extra_row_modifiers: List[RowModifier] = []


class BaseLineRowModifier(RowModifier):
    def __init__(self, justification_length: int = 0):
        self.justification_length = justification_length

    def apply(self, row: RowDefinition, justification_length: int):
        return RowDefinition(
            name=row.name.ljust(justification_length if justification_length else self.justification_length),
            text=row.text.strip().ljust(justification_length if justification_length else self.justification_length),
        )


class HighlightNewRowNameModifier(RowModifier):
    NEW_TEXT = "NEW!"
    NEW_COLOR = "bright_yellow"

    def apply(self, row: RowDefinition, justification_length: int):
        return RowDefinition(
            name=style(
                f"{row.name.strip() + ' ' + self.NEW_TEXT}".ljust(justification_length),
                bold=True,
                fg=self.NEW_COLOR,
            ),
            text=row.text.strip(),
        )


class ShowcaseRowModifier(RowModifier):
    COLOR = "green"

    def apply(self, row: RowDefinition, justification_length: int):
        return RowDefinition(
            name=style(
                f"{row.name}".ljust(justification_length),
                fg=self.COLOR,
            ),
            text=style(row.text.strip(), fg=self.COLOR),
        )
