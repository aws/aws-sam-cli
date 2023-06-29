"""
Class to represent the parsing of different file types into Python objects.
"""


import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Type

import tomlkit
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.compat import StringIO

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
            A dictionary-like representation of the contents at the filepath location.
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
            toml_document.add(tomlkit.comment(toml_document.get(COMMENT_KEY, "")))
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


class YamlFileManager(FileManager):
    """
    Static class to read and write yaml files.
    """

    yaml = YAML()
    file_format = "YAML"

    @staticmethod
    def read(filepath: Path) -> Any:
        """
        Read a YAML file at the given path.

        Parameters
        ----------
        filepath: Path
            The Path object that points to the file to be read.

        Returns
        -------
        Any
            A dictionary-like yaml object, which represents the contents of the YAML file at the
            provided location.
        """
        yaml_doc = {}
        try:
            yaml_doc = YamlFileManager.yaml.load(filepath.read_text())
        except OSError as e:
            LOG.debug(f"OSError occurred while reading {YamlFileManager.file_format} file: {str(e)}")
        except YAMLError as e:
            raise FileParseException(e) from e

        return yaml_doc

    @staticmethod
    def write(document: dict, filepath: Path):
        """
        Write the contents of a dictionary to a YAML file at the provided location.

        Parameters
        ----------
        document: dict
            The object to write.
        filepath: Path
            The final location for the YAML file to be written.
        """
        if not document:
            LOG.debug("No document given to YamlFileManager to write.")
            return

        yaml_doc = YamlFileManager._to_yaml(document)

        if yaml_doc.get(COMMENT_KEY, None):  # Comment appears at the top of doc
            yaml_doc.yaml_set_start_comment(document[COMMENT_KEY])
            yaml_doc.pop(COMMENT_KEY)

        YamlFileManager.yaml.dump(yaml_doc, filepath)

    @staticmethod
    def put_comment(document: Any, comment: str) -> Any:
        """
        Put a comment in a document object.

        Parameters
        ----------
        document: Any
            The yaml object to write
        comment: str
            The comment to include in the document.

        Returns
        -------
        Any
            The new yaml document, with the comment added to it.
        """
        document = YamlFileManager._to_yaml(document)
        document.yaml_set_start_comment(comment)
        return document

    @staticmethod
    def _to_yaml(document: dict) -> Any:
        """
        Ensure a dictionary-like object is a YAML document.

        Parameters
        ----------
        document: dict
            A dictionary-like object to parse.

        Returns
        -------
        Any
            A dictionary-like YAML object, as derived from `yaml.load()`.
        """
        with StringIO() as stream:
            YamlFileManager.yaml.dump(document, stream)
            return YamlFileManager.yaml.load(stream.getvalue())


class JsonFileManager(FileManager):
    """
    Static class to read and write json files.
    """

    file_format = "JSON"
    INDENT_SIZE = 2

    @staticmethod
    def read(filepath: Path) -> Any:
        """
        Read a JSON file at a given path.

        Parameters
        ----------
        filepath: Path
            The Path object that points to the file to be read.

        Returns
        -------
        Any
            A dictionary representation of the contents of the JSON document.
        """
        json_file = {}
        try:
            json_file = json.loads(filepath.read_text())
        except OSError as e:
            LOG.debug(f"OSError occurred while reading {JsonFileManager.file_format} file: {str(e)}")
        except json.JSONDecodeError as e:
            raise FileParseException(e) from e
        return json_file

    @staticmethod
    def write(document: dict, filepath: Path):
        """
        Write a dictionary or dictionary-like object to a JSON file.

        Parameters
        ----------
        document: dict
            The JSON object to write.
        filepath: Path
            The final location for the document to be written.
        """
        if not document:
            LOG.debug("No document given to JsonFileManager to write.")
            return

        with filepath.open("w") as file:
            json.dump(document, file, indent=JsonFileManager.INDENT_SIZE)

    @staticmethod
    def put_comment(document: Any, comment: str) -> Any:
        """
        Put a comment in a JSON object.

        Parameters
        ----------
        document: Any
            The JSON object to write
        comment: str
            The comment to include in the document.

        Returns
        -------
        Any
            The new JSON dictionary object, with the comment added to it.
        """
        document.update({COMMENT_KEY: comment})
        return document


FILE_MANAGER_MAPPER: Dict[str, Type[FileManager]] = {  # keys ordered by priority
    ".toml": TomlFileManager,
    ".yaml": YamlFileManager,
    ".yml": YamlFileManager,
    # ".json": JsonFileManager,  # JSON support disabled
}
