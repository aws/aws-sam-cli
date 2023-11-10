import json
from pathlib import Path
import tempfile
from unittest import TestCase, skip

import tomlkit
from ruamel.yaml import YAML

from samcli.lib.config.exceptions import FileParseException
from samcli.lib.config.file_manager import COMMENT_KEY, JsonFileManager, TomlFileManager, YamlFileManager


class TestTomlFileManager(TestCase):
    def test_read_toml(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.toml")
        config_path.write_text(
            "version=0.1\n[config_env.topic1.parameters]\nword='clarity'\nmultiword=['thing 1', 'thing 2']"
        )
        config_doc = TomlFileManager.read(config_path)
        self.assertEqual(
            config_doc,
            {
                "version": 0.1,
                "config_env": {"topic1": {"parameters": {"word": "clarity", "multiword": ["thing 1", "thing 2"]}}},
            },
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
        self.assertNotIn(COMMENT_KEY, txt)

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


class TestYamlFileManager(TestCase):
    yaml = YAML()

    def test_read_yaml(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.yaml")
        config_path.write_text(
            "version: 0.1\nconfig_env:\n  topic1:\n    parameters:\n      word: clarity\n      multiword: [thing 1, thing 2]"
        )

        config_doc = YamlFileManager.read(config_path)

        self.assertEqual(
            config_doc,
            {
                "version": 0.1,
                "config_env": {"topic1": {"parameters": {"word": "clarity", "multiword": ["thing 1", "thing 2"]}}},
            },
        )

    def test_read_yaml_invalid_yaml(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.yaml")
        config_path.write_text("fake: not real\nthisYaml isn't correct")

        with self.assertRaises(FileParseException):
            YamlFileManager.read(config_path)

    def test_read_yaml_file_path_not_valid(self):
        config_dir = "path/that/doesnt/exist"
        config_path = Path(config_dir, "samconfig.yaml")

        config_doc = YamlFileManager.read(config_path)

        self.assertEqual(config_doc, {})

    def test_write_yaml(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.yaml")
        yaml = {
            "version": 0.1,
            "config_env": {"topic2": {"parameters": {"word": "clarity"}}},
            COMMENT_KEY: "This is a comment",
        }

        YamlFileManager.write(yaml, config_path)

        txt = config_path.read_text()
        self.assertIn("version: 0.1", txt)
        self.assertIn("config_env:\n  topic2:\n    parameters:\n", txt)
        self.assertIn("word: clarity", txt)
        self.assertIn("# This is a comment", txt)
        self.assertNotIn(COMMENT_KEY, txt)

    def test_dont_write_yaml_if_empty(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.yaml")
        config_path.write_text("nothing to see here\n")
        yaml = {}

        YamlFileManager.write(yaml, config_path)

        self.assertEqual(config_path.read_text(), "nothing to see here\n")

    def test_write_yaml_file_bad_path(self):
        config_path = Path("path/to/some", "file_that_doesnt_exist.yaml")

        with self.assertRaises(FileNotFoundError):
            YamlFileManager.write(self.yaml.load("key: some value"), config_path)

    def test_yaml_put_comment(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.yaml")
        yaml_doc = self.yaml.load("version: 0.1\nconfig_env:\n  topic2:\n    parameters:\n      word: clarity\n")

        yaml_doc = YamlFileManager.put_comment(yaml_doc, "This is a comment")

        self.yaml.dump(yaml_doc, config_path)
        txt = config_path.read_text()
        self.assertIn("# This is a comment", txt)


@skip("JSON config support disabled")
class TestJsonFileManager(TestCase):
    def test_read_json(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.json")
        config_path.write_text(
            json.dumps(
                {
                    "version": 0.1,
                    "config_env": {"topic1": {"parameters": {"word": "clarity", "multiword": ["thing 1", "thing 2"]}}},
                },
                indent=JsonFileManager.INDENT_SIZE,
            )
        )

        config_doc = JsonFileManager.read(config_path)

        self.assertEqual(
            config_doc,
            {
                "version": 0.1,
                "config_env": {"topic1": {"parameters": {"word": "clarity", "multiword": ["thing 1", "thing 2"]}}},
            },
        )

    def test_read_json_invalid_json(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.json")
        config_path.write_text("{\n" + '  "bad_file": "very bad"\n' + '  "improperly": "formatted"\n' + "}\n")

        with self.assertRaises(FileParseException):
            JsonFileManager.read(config_path)

    def test_read_json_file_path_not_valid(self):
        config_dir = "path/that/doesnt/exist"
        config_path = Path(config_dir, "samconfig.json")

        config_doc = JsonFileManager.read(config_path)

        self.assertEqual(config_doc, {})

    def test_write_json(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.json")
        json_doc = {
            "version": 0.1,
            "config_env": {"topic2": {"parameters": {"word": "clarity"}}},
            COMMENT_KEY: "This is a comment",
        }

        JsonFileManager.write(json_doc, config_path)

        txt = config_path.read_text()
        self.assertIn('"version": 0.1', txt)
        self.assertIn('"config_env": {', txt)
        self.assertIn('"topic2": {', txt)
        self.assertIn('"parameters": {', txt)
        self.assertIn('"word": "clarity"', txt)
        self.assertIn(f'"{COMMENT_KEY}": "This is a comment"', txt)

    def test_dont_write_json_if_empty(self):
        config_dir = tempfile.gettempdir()
        config_path = Path(config_dir, "samconfig.json")
        config_path.write_text("nothing to see here\n")
        json_doc = {}

        JsonFileManager.write(json_doc, config_path)

        self.assertEqual(config_path.read_text(), "nothing to see here\n")

    def test_write_json_file_bad_path(self):
        config_path = Path("path/to/some", "file_that_doesnt_exist.json")

        with self.assertRaises(FileNotFoundError):
            JsonFileManager.write({"key": "value"}, config_path)

    def test_json_put_comment(self):
        json_doc = {"version": 0.1, "config_env": {"topic1": {"parameters": {"word": "clarity"}}}}

        json_doc = JsonFileManager.put_comment(json_doc, "This is a comment")

        txt = json.dumps(json_doc)
        self.assertIn(f'"{COMMENT_KEY}": "This is a comment"', txt)
