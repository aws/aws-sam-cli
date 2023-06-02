from pathlib import Path
import tempfile
from unittest import TestCase

import tomlkit
from samcli.lib.config.exceptions import FileParseException

from samcli.lib.config.file_manager import COMMENT_KEY, TomlFileManager


class TestTomlFileManager(TestCase):
    def test_read_toml(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("version=0.1\n[config_env.topic1.parameters]\nword='clarity'\n")
        config_doc = TomlFileManager.read(config_path)
        self.assertEqual(
            config_doc,
            {"version": 0.1, "config_env": {"topic1": {"parameters": {"word": "clarity"}}}},
        )

    def test_read_toml_invalid_toml(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("fake='not real'\nimproper toml file\n")
        with self.assertRaises(FileParseException):
            TomlFileManager.read(config_path)

    def test_read_toml_file_path_not_valid(self):
        config_dir = "path/that/doesnt/exist"
        config_path = Path(config_dir, "samconfig.toml")
        config_doc = TomlFileManager.read(config_path)
        self.assertEqual(config_doc, tomlkit.document())

    def test_write_toml(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        toml = {
            "version": 0.1,
            "config_env": {"topic2": {"parameters": {"word": "clarity"}}},
            COMMENT_KEY: "This is a comment",
        }

        TomlFileManager.write(toml, config_path)

        txt = config_path.read_text()
        self.assertIn("version = 0.1", txt)
        self.assertIn("[config_env.topic2.parameters]", txt)
        self.assertIn('word = "clarity"', txt)
        self.assertIn("# This is a comment", txt)

    def test_dont_write_toml_if_empty(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("nothing to see here\n")
        toml = {}

        TomlFileManager.write(toml, config_path)

        self.assertEqual(config_path.read_text(), "nothing to see here\n")

    def test_write_toml_bad_path(self):
        config_path = Path("path/to/some", "file_that_doesnt_exist.toml")
        with self.assertRaises(FileNotFoundError):
            TomlFileManager.write({"key": "some value"}, config_path)

    def test_write_toml_file(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        toml = tomlkit.parse('# This is a comment\nversion = 0.1\n[config_env.topic2.parameters]\nword = "clarity"\n')

        TomlFileManager.write(toml, config_path)

        txt = config_path.read_text()
        self.assertIn("version = 0.1", txt)
        self.assertIn("[config_env.topic2.parameters]", txt)
        self.assertIn('word = "clarity"', txt)
        self.assertIn("# This is a comment", txt)

    def test_dont_write_toml_file_if_empty(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text("nothing to see here\n")
        toml = tomlkit.document()

        TomlFileManager.write(toml, config_path)

        self.assertEqual(config_path.read_text(), "nothing to see here\n")

    def test_write_toml_file_bad_path(self):
        config_path = Path("path/to/some", "file_that_doesnt_exist.toml")
        with self.assertRaises(FileNotFoundError):
            TomlFileManager.write(tomlkit.parse('key = "some value"'), config_path)

    def test_toml_put_comment(self):
        toml_doc = tomlkit.loads('version = 0.1\n[config_env.topic2.parameters]\nword = "clarity"\n')

        toml_doc = TomlFileManager.put_comment(toml_doc, "This is a comment")

        txt = tomlkit.dumps(toml_doc)
        self.assertIn("# This is a comment", txt)
