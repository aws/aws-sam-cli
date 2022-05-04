"""
Generic table view interface
"""
from abc import ABC, abstractmethod
from typing import List, Dict


class AbstractTable(ABC):

    @abstractmethod
    def add_column(self, title: str, options: Dict[str, str]) -> None:
        """
        Add a column to the table
        :param title: Column title
        :param options: Styling options to give the column
        """

    @abstractmethod
    def add_row(self, data: List[str]) -> None:
        """
        Add a row to the table.
        :param data: List of data. Should correspond with table columns
        """

    @abstractmethod
    def print(self) -> None:
        """
        Prints the table to stdout
        """