"""
Class to represent the parsing of different file types into Python objects.
"""


import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import tomlkit

from samcli.lib.config.exceptions import FileParseException

LOG = logging.getLogger(__name__)


class FileManager(ABC):
    """
    Abstract class to be overridden by file managers for specific file extensions.
    """

    @staticmethod
    @abstractmethod
    def read(filepath: Path) -> Any:
        """
        Read a file at a given path.

        Parameters
        ----------
        filepath: Path
            The Path object that points to the file to be read.

        Returns
        -------
        Any
            A dictionary-like representation of the contents at the filepath location, along with a specialized
            representation of the file that was read, if there is a specialization of it.
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

    @staticmethod
    @abstractmethod
    def write_document(document: Any, filepath: Path):
        """
        Write the contents of a document object to a file at the provided location.

        Parameters
        ----------
        document: Any
            The object to write.
        filepath: Path
            The final location for the file to be written.
        """
        raise NotImplementedError("Write document method not implemented.")


class TomlFileManager(FileManager):
    """
    Static class to read and write toml files.
    """

    @staticmethod
    def read(filepath: Path) -> Any:
        """
        Read a TOML file at the given path.

        Parameters
        ----------
        filepath: Path
            The Path object that points to the file to be read.

        Returns
        -------
        Any
            A dictionary-like tomlkit.TOMLDocument object, which represents the contents of the TOML file at the
            provided location.
        """
        toml_doc = tomlkit.document()
        try:
            txt = filepath.read_text()
            toml_doc = tomlkit.loads(txt)
        except OSError as e:
            LOG.debug(f"OSError occurred while reading TOML file: {str(e)}")
        except tomlkit.exceptions.TOMLKitError as e:
            raise FileParseException(e) from e

        return toml_doc

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

        doc_no_comments = {k: v for k, v in document.items() if k != "__comment__"}
        toml_doc = tomlkit.document()

        if document.get("__comment__", None):  # Comment appears at the top of doc
            toml_doc.add(tomlkit.comment(document["__comment__"]))
        for k, v in doc_no_comments.items():
            toml_doc.add(k, v)

        filepath.write_text(tomlkit.dumps(toml_doc))

    @staticmethod
    def write_document(document: Any, filepath: Path):
        """
        Write the contents of a tomlkit.TOMLDocument object to a TOML file at the provided location.

        Parameters
        ----------
        document: Any
            The object to write.
        filepath: Path
            The final location for the TOML file to be written.
        """
        if not document:
            LOG.debug("No TOMLDocument given for TomlFileManager to write.")
            return

        filepath.write_text(tomlkit.dumps(document))
