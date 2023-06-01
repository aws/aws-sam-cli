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
COMMENT_KEY = "__comment__"


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
        Write a dictionary or dictionary-like object to a given file.

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
    def put_comment(document: Any, comment: str) -> Any:
        """
        Put a comment in a document object.

        Parameters
        ----------
        document: Any
            The object to write
        comment: str
            The comment to include in the document.

        Returns
        -------
        Any
            The new document, with the comment added to it.
        """
        raise NotImplementedError("Put comment method not implemented.")


class TomlFileManager(FileManager):
    """
    Static class to read and write toml files.
    """

    file_format = "TOML"

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
            LOG.debug(f"OSError occurred while reading {TomlFileManager.file_format} file: {str(e)}")
        except tomlkit.exceptions.TOMLKitError as e:
            raise FileParseException(e) from e

        return toml_doc

    @staticmethod
    def write(document: dict, filepath: Path):
        """
        Write the contents of a dictionary or tomlkit.TOMLDocument to a TOML file at the provided location.

        Parameters
        ----------
        document: dict
            The object to write.
        filepath: Path
            The final location for the TOML file to be written.
        """
        if not document:
            LOG.debug("Nothing for TomlFileManager to write.")
            return

        toml_document = TomlFileManager._to_toml(document)

        if toml_document.get(COMMENT_KEY, None):  # Remove dunder comments that may be residue from other formats
            toml_document.add(tomlkit.comment(toml_document[COMMENT_KEY]))
            toml_document.pop(COMMENT_KEY)

        filepath.write_text(tomlkit.dumps(toml_document))

    @staticmethod
    def put_comment(document: dict, comment: str) -> Any:
        """
        Put a comment in a document object.

        Parameters
        ----------
        document: Any
            The tomlkit.TOMLDocument object to write
        comment: str
            The comment to include in the document.

        Returns
        -------
        Any
            The new TOMLDocument, with the comment added to it.
        """
        document = TomlFileManager._to_toml(document)
        document.add(tomlkit.comment(comment))
        return document

    @staticmethod
    def _to_toml(document: dict) -> tomlkit.TOMLDocument:
        """Ensure that a dictionary-like object is a TOMLDocument."""
        return tomlkit.parse(tomlkit.dumps(document))
