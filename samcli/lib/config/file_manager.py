"""
Class to represent the parsing of different file types into Python objects.
"""


import logging
from abc import ABC, abstractmethod
from pathlib import Path

import tomlkit

from samcli.lib.config.exceptions import FileParseException

LOG = logging.getLogger(__name__)


class FileManager(ABC):
    """
    Abstract class to be overridden by file managers for specific file extensions.
    """

    @staticmethod
    @abstractmethod
    def read(filepath: Path) -> dict:
        """
        Read a file at a given path.

        Parameters
        ----------
        filepath: Path
            The Path object that points to the file to be read.

        Returns
        -------
        dict
            The dictionary representation of the contents at the filepath location.
        """
        raise NotImplementedError("Read method not implemented.")

    @staticmethod
    @abstractmethod
    def write(document: dict, filepath: Path):
        """
        Write a dictionary to a given file.

        Parameters
        ----------
        document: dict
            The object to write.
        filepath: Path
            The final location for the document to be written.
        """
        raise NotImplementedError("Write method not implemented.")


class TomlFileManager(FileManager):
    """
    Static class to read and write toml files.
    """

    @staticmethod
    def read(filepath: Path) -> dict:
        """
        Read a TOML file at the given path.

        Parameters
        ----------
        filepath: Path
            The Path object that points to the file to be read.

        Returns
        -------
        dict
            A Python dictionary representation of the contents of the TOML file at the provided location.
        """
        document: dict = {}
        try:
            txt = filepath.read_text()
            document = dict(tomlkit.loads(txt))
        except OSError as e:
            LOG.debug(f"OSError occurred while reading TOML file: {str(e)}")
            document = {}
        except tomlkit.exceptions.TOMLKitError as e:
            raise FileParseException(e) from e

        return document

    @staticmethod
    def write(document: dict, filepath: Path):
        """
        Write the contents of a dictionary to a TOML file at the provided location.

        Parameters
        ----------
        document: dict
            The object to write.
        filepath: Path
            The final location for the TOML file to be written.
        """
        if not document:
            LOG.debug("No document given for TomlFileManager to write.")
            return

        filepath.write_text(tomlkit.dumps(document))
