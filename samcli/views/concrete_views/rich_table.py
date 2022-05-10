"""
Implementation of table view using the Rich terminal library
"""
from typing import List, Dict, Optional, Any

from rich.console import Console
from rich.table import Table
from samcli.views.table_view import AbstractTable


class RichTable(AbstractTable):
    def __init__(self, title: str, table_options: Optional[Dict[Any, Any]] = None):
        """
        Instantiate a Rich table
        :param title: name of the table
        """
        self._title = title
        self._table = Table(title=title, **table_options) if table_options else Table(title=title)
        self._console = Console()

    def add_column(self, title: str, options: Optional[Dict[Any, Any]] = None) -> None:
        """
        Add a column to a rich table
        :param title: column title
        :param options: style object should contain styling properties as defined by the Rich library
        """
        if options:
            self._table.add_column(title, **options)
        else:
            self._table.add_column(title)

    def add_row(self, data: List[str]) -> None:
        """
        Add a row to a rich table
        :param data: data to be displayed given as a list of strings, where each string corresponds to a column
        """
        self._table.add_row(*data)

    def print(self) -> None:
        """
        Print the table to stdout
        """
        self._console.print(self._table)
