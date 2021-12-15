from parameterized import parameterized
from unittest.case import TestCase
from unittest.mock import MagicMock, patch, ANY
from samcli.lib.utils.definition_validator import DefinitionValidator


class TestDefinitionValidator(TestCase):
    def setUp(self) -> None:
        self.path = MagicMock()

    @patch("samcli.lib.utils.definition_validator.parse_yaml_file")
    def test_invalid_path(self, parse_yaml_file_mock):
        parse_yaml_file_mock.side_effect = [{"A": 1}, {"A": 1}]
        self.path.exists.return_value = False

        validator = DefinitionValidator(self.path, detect_change=False, initialize_data=False)
        self.assertFalse(validator.validate())
        self.assertFalse(validator.validate())

    @patch("samcli.lib.utils.definition_validator.parse_yaml_file")
    def test_no_detect_change_valid(self, parse_yaml_file_mock):
        parse_yaml_file_mock.side_effect = [{"A": 1}, {"A": 1}]

        validator = DefinitionValidator(self.path, detect_change=False, initialize_data=False)
        self.assertTrue(validator.validate())
        self.assertTrue(validator.validate())

    @patch("samcli.lib.utils.definition_validator.parse_yaml_file")
    def test_no_detect_change_invalid(self, parse_yaml_file_mock):
        parse_yaml_file_mock.side_effect = [ValueError(), {"A": 1}]

        validator = DefinitionValidator(self.path, detect_change=False, initialize_data=False)
        self.assertFalse(validator.validate())
        self.assertTrue(validator.validate())

    @patch("samcli.lib.utils.definition_validator.parse_yaml_file")
    def test_detect_change_valid(self, parse_yaml_file_mock):
        parse_yaml_file_mock.side_effect = [{"A": 1}, {"B": 1}]

        validator = DefinitionValidator(self.path, detect_change=True, initialize_data=False)
        self.assertTrue(validator.validate())
        self.assertTrue(validator.validate())

    @patch("samcli.lib.utils.definition_validator.parse_yaml_file")
    def test_detect_change_invalid(self, parse_yaml_file_mock):
        parse_yaml_file_mock.side_effect = [{"A": 1}, {"A": 1}, ValueError(), {"B": 1}]

        validator = DefinitionValidator(self.path, detect_change=True, initialize_data=False)
        self.assertTrue(validator.validate())
        self.assertFalse(validator.validate())
        self.assertFalse(validator.validate())
        self.assertTrue(validator.validate())

    @patch("samcli.lib.utils.definition_validator.parse_yaml_file")
    def test_detect_change_initialize(self, parse_yaml_file_mock):
        parse_yaml_file_mock.side_effect = [{"A": 1}, {"A": 1}, ValueError(), {"B": 1}]

        validator = DefinitionValidator(self.path, detect_change=True, initialize_data=True)
        self.assertFalse(validator.validate())
        self.assertFalse(validator.validate())
        self.assertTrue(validator.validate())
