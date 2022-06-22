"""Test Hook Warpper"""
import json
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open, Mock

from samcli.lib.hook.hook_wrapper import IacHookWrapper
from samcli.lib.hook.hook_config import (
    HookFunctionalityParam,
    HookFunctionality, 
    HookPackageConfig
)
from samcli.lib.hook.exceptions import (
    InvalidHookWrapperException,
    InvalidHookPackageConfigException
)

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
                    "type": "array"
                },
                {
                    "long_name": "param2",
                    "short_name": "p2",
                    "description": "Parameter 2",
                    "mandatory": False,
                    "type": "array"
                },
            ]
        }
    }
}


class TestIacHookWrapper(TestCase):
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_validate_params_success(self, load_hook_package_mock):
        provided_params = {
            "param1": "value1",
            "p2": "value2",
            "param3": ["value3a", "value3b"]
        }
        functionality = HookFunctionality(
            "main",
            [
                HookFunctionalityParam("param1", "p1", "description", True, "string"),
                HookFunctionalityParam("param2", "p2", "description", True, "string"),
                HookFunctionalityParam("param3", "p3", "description", True, "string"),
            ]
        )
        hook_wrapper = IacHookWrapper("test_id")
        result = hook_wrapper._validate_params(functionality, provided_params)
        self.assertIsNone(result)

    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_validate_params_fail(self, load_hook_package_mock):
        provided_params = {
            "param1": "value1",
        }
        functionality = HookFunctionality(
            "main",
            [
                HookFunctionalityParam("param1", "p1", "description", True, "string"),
                HookFunctionalityParam("param2", "p2", "description", True, "string"),
                HookFunctionalityParam("param3", "p3", "description", True, "string"),
            ]
        )
        hook_wrapper = IacHookWrapper("test_id")
        with self.assertRaises(InvalidHookWrapperException) as e:
            hook_wrapper._validate_params(functionality, provided_params)
        self.assertEqual(e.exception.message, "Missing required parameters param2, param3")

    @patch("samcli.lib.hook.hook_wrapper.platform")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_get_entry_script_executable_non_windows(self, load_hook_package_mock, platform_mock):
        platform_mock.system.return_value = "Darwin"
        functionality = HookFunctionality("some_entry_script", None)
        hook_wrapper = IacHookWrapper("test_id")
        hook_wrapper._config = Mock()
        hook_wrapper._config.package_dir = Path("/my/path")
        entry_script_executable = hook_wrapper._get_entry_script_executable(functionality)
        self.assertEqual(entry_script_executable, "/my/path/some_entry_script.sh")

    @patch("samcli.lib.hook.hook_wrapper.platform")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_get_entry_script_executable_windows(self, load_hook_package_mock, platform_mock):
        platform_mock.system.return_value = "Windows"
        functionality = HookFunctionality("some_entry_script", None)
        hook_wrapper = IacHookWrapper("test_id")
        hook_wrapper._config = Mock()
        hook_wrapper._config.package_dir = Path("/my/path")
        entry_script_executable = hook_wrapper._get_entry_script_executable(functionality)
        self.assertEqual(entry_script_executable, "/my/path/some_entry_script.bat")

    @patch("samcli.lib.hook.hook_wrapper.HookPackageConfig")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._INTERNAL_PACKAGES_ROOT")
    def test_instantiate_success(self, _INTERNAL_PACKAGES_ROOT_MOCK, HookPackageConfigMock):
        _INTERNAL_PACKAGES_ROOT_MOCK.iterdir.return_value = [
            "hook_package_1",
            "hook_package_2",
            "hook_package_3",
        ]
        hook_package_1_config_mock = Mock()
        hook_package_1_config_mock.package_id = "hook-package-1"
        hook_package_2_config_mock = Mock()
        hook_package_2_config_mock.package_id = "hook-package-2"
        hook_package_3_config_mock = Mock()
        hook_package_3_config_mock.package_id = "hook-package-3"

        HookPackageConfigMock.side_effect = [
            hook_package_1_config_mock,
            hook_package_2_config_mock,
            hook_package_3_config_mock,
        ]

        hook_package = IacHookWrapper("hook-package-3")
        self.assertEqual(hook_package._config, hook_package_3_config_mock)

    @patch("samcli.lib.hook.hook_wrapper.HookPackageConfig")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._INTERNAL_PACKAGES_ROOT")
    def test_instantiate_package_not_found(self, _INTERNAL_PACKAGES_ROOT_MOCK, HookPackageConfigMock):
        _INTERNAL_PACKAGES_ROOT_MOCK.iterdir.return_value = [
            "hook_package_1",
            "hook_package_2",
            "hook_package_3",
        ]
        hook_package_1_config_mock = Mock()
        hook_package_1_config_mock.package_id = "hook-package-1"
        hook_package_2_config_mock = Mock()
        hook_package_2_config_mock.package_id = "hook-package-2"
        hook_package_3_config_mock = Mock()
        hook_package_3_config_mock.package_id = "hook-package-3"

        HookPackageConfigMock.side_effect = [
            hook_package_1_config_mock,
            hook_package_2_config_mock,
            hook_package_3_config_mock,
        ]

        with self.assertRaises(InvalidHookWrapperException) as e:
            IacHookWrapper("hook-package-4")
        
        self.assertEqual(
            e.exception.message,
            'Cannot locate hook package with hook_package_id "hook-package-4"'
        )

    @patch("samcli.lib.hook.hook_wrapper.HookPackageConfig")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._INTERNAL_PACKAGES_ROOT")
    def test_instantiate_success_with_invalid_package(self, _INTERNAL_PACKAGES_ROOT_MOCK, HookPackageConfigMock):
        _INTERNAL_PACKAGES_ROOT_MOCK.iterdir.return_value = [
            "hook_package_1",
            "hook_package_2",
            "hook_package_3",
        ]
        hook_package_1_config_mock = Mock()
        hook_package_1_config_mock.package_id = "hook-package-1"
        hook_package_3_config_mock = Mock()
        hook_package_3_config_mock.package_id = "hook-package-3"

        HookPackageConfigMock.side_effect = [
            hook_package_1_config_mock,
            InvalidHookPackageConfigException("Invalid config"),
            hook_package_3_config_mock,
        ]

        hook_package = IacHookWrapper("hook-package-3")
        self.assertEqual(hook_package._config, hook_package_3_config_mock)


        
        

