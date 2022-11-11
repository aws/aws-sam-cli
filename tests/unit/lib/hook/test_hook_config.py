"""Test Hook Package Config"""
import json
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open

from samcli.lib.hook.hook_config import HookFunctionality, HookPackageConfig
from samcli.lib.hook.exceptions import InvalidHookPackageConfigException

TEST_HOOK_PACKAGE_CONFIG = {
    "hook_name": "my_test_hook_name",
    "hook_use_case": "IaC",
    "description": "testing",
    "version": "1.0.0",
    "hook_specification": "1.0.0",
    "functionalities": {
        "prepare": {
            "entry_method": {
                "module": "x.y.z",
                "method": "my_method",
            },
        }
    },
}


class TestHookFunctionality(TestCase):
    def setUp(self) -> None:
        self._config = deepcopy(TEST_HOOK_PACKAGE_CONFIG)

    def test_create_functionality(self):
        prepare_dict = self._config["functionalities"]["prepare"]
        functionality = HookFunctionality(prepare_dict["entry_method"])
        self.assertEqual(functionality.module, "x.y.z")
        self.assertEqual(functionality.method, "my_method")


class TestHookPackageConfig(TestCase):
    def setUp(self) -> None:
        self._config = deepcopy(TEST_HOOK_PACKAGE_CONFIG)

    def test_valid_config(self):
        package_path_mock = MagicMock(name="package_path_mock")
        config_loc_mock = MagicMock(name="config_loc_mock")
        config_loc_mock.is_file.return_value = True
        config_loc_mock.open = mock_open(read_data=json.dumps(self._config))
        package_path_mock.__truediv__.return_value = config_loc_mock

        hook_config = HookPackageConfig(package_path_mock)
        self.assertEqual(hook_config.name, self._config["hook_name"])
        self.assertEqual(hook_config.use_case, self._config["hook_use_case"])
        self.assertEqual(hook_config.version, self._config["version"])
        self.assertEqual(hook_config.specification, self._config["hook_specification"])
        self.assertEqual(hook_config.description, self._config["description"])

        self.assertIn("prepare", hook_config.functionalities)
        self.assertIsInstance(hook_config.functionalities["prepare"], HookFunctionality)

    def test_invalid_config(self):
        invalid_config = deepcopy(self._config)
        invalid_config["version"] = "1.x.y"

        package_path_mock = MagicMock(name="package_path_mock")
        config_loc_mock = MagicMock(name="config_loc_mock")
        config_loc_mock.is_file.return_value = True
        config_loc_mock.open = mock_open(read_data=json.dumps(invalid_config))
        package_path_mock.__truediv__.return_value = config_loc_mock

        with self.assertRaises(InvalidHookPackageConfigException) as e:
            HookPackageConfig(package_path_mock)

        self.assertTrue(e.exception.message.startswith("Invalid Config.json - "))

    def test_missing_both_entry_method(self):
        config_dict = {
            "hook_name": "my_test_hook_name",
            "hook_use_case": "IaC",
            "description": "testing",
            "version": "1.0.0",
            "hook_specification": "1.0.0",
            "functionalities": {"prepare": {}},
        }

        package_path_mock = MagicMock(name="package_path_mock")
        config_loc_mock = MagicMock(name="config_loc_mock")
        config_loc_mock.is_file.return_value = True
        config_loc_mock.open = mock_open(read_data=json.dumps(config_dict))
        package_path_mock.__truediv__.return_value = config_loc_mock

        with self.assertRaises(InvalidHookPackageConfigException) as e:
            HookPackageConfig(package_path_mock)

        self.assertTrue(e.exception.message.startswith("Invalid Config.json - 'entry_method' is a required property"))

    def test_non_existent_config(self):
        package_path_mock = MagicMock(name="package_path_mock")
        config_loc_mock = MagicMock(name="config_loc_mock")
        config_loc_mock.is_file.return_value = False
        config_loc_mock.__str__.return_value = "fake_path/Config.json"
        package_path_mock.__truediv__.return_value = config_loc_mock

        with self.assertRaises(InvalidHookPackageConfigException) as e:
            HookPackageConfig(package_path_mock)

        self.assertEqual(e.exception.message, "fake_path/Config.json is not a file or does not exist")
