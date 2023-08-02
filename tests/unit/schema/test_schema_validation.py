import os
from pathlib import Path
import jsonschema
from parameterized import parameterized
from unittest import TestCase

from samcli.lib.config.file_manager import FILE_MANAGER_MAPPER
from schema.make_schema import generate_schema


class TestSchemaValidation(TestCase):
    schema = None
    testdata_dir = None

    @classmethod
    def setUpClass(cls):
        cls.schema = generate_schema()
        testing_dir = Path(__name__).resolve().parents[0]
        cls.testdata_dir = str(Path(testing_dir, "tests", "unit", "schema", "testdata"))

    def test_samconfig_validates_against_schema(self):
        self.assertIsNotNone(self.schema, "Schema was not set")

        passing_tests_dir = Path(self.testdata_dir, "passing_tests")

        # Read in and assert all files in passing_tests pass
        for config_file_path in os.listdir(passing_tests_dir):
            config_file = FILE_MANAGER_MAPPER[Path(config_file_path).suffix].read(
                Path(str(passing_tests_dir), config_file_path)
            )
            self.assertNotEqual(config_file, {}, f"Config file {config_file_path} should be read correctly")

            try:
                jsonschema.validate(config_file, self.schema)
            except jsonschema.ValidationError as e:
                self.fail(f"File {config_file_path} not validating: {e.message}")

    def test_samconfig_doesnt_validate_against_schema(self):
        self.assertIsNotNone(self.schema, "Schema was not set")

        failing_tests_dir = Path(self.testdata_dir, "failing_tests")

        # Read in and assert all files in failing_tests fail
        for config_file_path in os.listdir(failing_tests_dir):
            config_file = FILE_MANAGER_MAPPER[Path(config_file_path).suffix].read(
                Path(str(failing_tests_dir), config_file_path)
            )
            self.assertNotEqual(config_file, {}, f"Config file {config_file_path} should be read correctly")

            with self.assertRaises(
                jsonschema.ValidationError, msg=f"Config file {config_file_path} should not validate against schema"
            ):
                jsonschema.validate(config_file, self.schema)
