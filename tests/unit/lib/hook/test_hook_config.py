"""Test Hook Package Config"""
import json
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open

from samcli.lib.hook.hook_config import HookFunctionalityParam, HookFunctionality, HookPackageConfig
from samcli.lib.hook.exceptions import InvalidHookPackageConfigException

TEST_HOOK_PACKAGE_CONFIG = {
    "hook_package_id": "my_test_hook_package_id",
    "hook_use_case": "IaC",
    "description": "testing",
    "version": "1.0.0",
    "hook_specification": "1.0.0",
    "functionalities": {
        "prepare": {
            "entry_script": "./prepare/main",
            "parameters": [
                {
                    "long_name": "param1",
                    "short_name": "p1",
                    "description": "Parameter 1",
                    "mandatory": True,
                    "type": "array",
                },
                {
                    "long_name": "param2",
                    "short_name": "p2",
                    "description": "Parameter 2",
                    "mandatory": False,
                    "type": "array",
                },
            ],
        }
    },
}


class TestHookFunctionality(TestCase):
    def setUp(self) -> None:
        self._config = deepcopy(TEST_HOOK_PACKAGE_CONFIG)

    def test_mandatory_parameters(self):
        prepare_dict = self._config["functionalities"]["prepare"]
        params = [HookFunctionalityParam(**param) for param in prepare_dict["parameters"]]
        functionality = HookFunctionality(prepare_dict["entry_script"], params)
        expected = [HookFunctionalityParam("param1", "p1", "Parameter 1", True, "array")]

        self.assertEqual(functionality.mandatory_parameters, expected)


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
        self.assertEqual(hook_config.package_id, self._config["hook_package_id"])
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

    def test_non_existent_config(self):
        package_path_mock = MagicMock(name="package_path_mock")
        config_loc_mock = MagicMock(name="config_loc_mock")
        config_loc_mock.is_file.return_value = False
        config_loc_mock.__str__.return_value = "fake_path/Config.json"
        package_path_mock.__truediv__.return_value = config_loc_mock

        with self.assertRaises(InvalidHookPackageConfigException) as e:
            HookPackageConfig(package_path_mock)

        self.assertEqual(e.exception.message, "fake_path/Config.json is not a file or does not exist")
