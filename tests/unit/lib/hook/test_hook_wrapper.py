"""Test Hook Warpper"""
from asyncio import subprocess
import json
from copy import deepcopy
from pathlib import Path
from sys import stderr, stdin
from unittest import TestCase
from unittest.mock import patch, MagicMock, mock_open, Mock

from samcli.lib.hook.hook_wrapper import IacHookWrapper, _execute_as_module
from samcli.lib.hook.exceptions import (
    InvalidHookWrapperException,
    InvalidHookPackageConfigException,
    HookPackageExecuteFunctionalityException,
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


class TestIacHookWrapper(TestCase):
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

        self.assertEqual(e.exception.message, 'Cannot locate hook package with hook_package_id "hook-package-4"')

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

    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_execute_functionality_not_exist(self, load_hook_package_mock):
        hook_wrapper = IacHookWrapper("test_id")
        hook_wrapper._config = Mock()
        hook_wrapper._config.package_dir = Path("/my/path")
        hook_wrapper._config.functionalities = {
            "prepare": Mock(),
        }

        with self.assertRaises(HookPackageExecuteFunctionalityException) as e:
            hook_wrapper._execute("other_key")

        self.assertEqual(e.exception.message, 'Functionality "other_key" is not defined in the hook package')

    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    @patch("samcli.lib.hook.hook_wrapper._execute_as_module")
    def test_execute_success(self, execute_as_module_mock, load_hook_package_mock):
        hook_wrapper = IacHookWrapper("test_id")
        hook_wrapper._config = Mock()
        hook_wrapper._config.package_dir = Path("/my/path")
        prepare_mock = Mock()
        prepare_mock.module = "x.y.z"
        prepare_mock.method = "my_method"
        hook_wrapper._config.functionalities = {
            "prepare": prepare_mock,
        }
        execute_as_module_mock.return_value = {"foo": "bar"}

        output = hook_wrapper._execute("prepare")
        self.assertEqual(output, {"foo": "bar"})
        execute_as_module_mock.assert_called_once_with("x.y.z", "my_method", None)

    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_execute_with_none_config(self, load_hook_package_mock):
        hook_wrapper = IacHookWrapper("test_id")
        hook_wrapper._config = None

        with self.assertRaises(InvalidHookWrapperException) as e:
            hook_wrapper._execute("prepare")

        self.assertEqual(e.exception.message, "Config is missing. You must instantiate a hook with a valid config")

    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    @patch("samcli.lib.hook.hook_wrapper._execute_as_module")
    def test_execute_with_missing_entry_method(self, execute_as_module_mock, load_hook_package_mock):
        hook_wrapper = IacHookWrapper("test_id")
        hook_wrapper._config = Mock()
        hook_wrapper._config.package_dir = Path("/my/path")
        prepare_mock = Mock()
        prepare_mock.entry_method = None
        hook_wrapper._config.functionalities = {
            "prepare": prepare_mock,
        }

        with self.assertRaises(InvalidHookWrapperException) as e:
            hook_wrapper._execute("prepare")

        self.assertEqual(e.exception.message, 'Functionality "prepare" is missing an "entry_method"')

    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._execute")
    def test_prepare_with_no_defaults(self, execute_mock, load_hook_package_mock):
        hook_wrapper = IacHookWrapper("test_id")
        execute_mock.return_value = {
            "Header": {},
            "IACApplications": {
                "MainApplication": {
                    "Metadata": "path/to/metadata",
                },
            },
        }
        actual = hook_wrapper.prepare(
            "path/to/output_dir", "path/to/iac_project", True, "path/to/logs", "my_profile", "us-east-1"
        )
        execute_mock.assert_called_once_with(
            "prepare",
            {
                "IACProjectPath": "path/to/iac_project",
                "OutputDirPath": "path/to/output_dir",
                "Debug": True,
                "LogsPath": "path/to/logs",
                "Profile": "my_profile",
                "Region": "us-east-1",
            },
        )
        self.assertEqual(actual, "path/to/metadata")

    @patch("samcli.lib.hook.hook_wrapper.Path.cwd")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._execute")
    def test_prepare_with_defaults(self, execute_mock, load_hook_package_mock, cwd_mock):
        cwd_mock.return_value = "path/to/cwd"
        hook_wrapper = IacHookWrapper("test_id")
        execute_mock.return_value = {
            "Header": {},
            "IACApplications": {
                "MainApplication": {
                    "Metadata": "path/to/metadata",
                },
            },
        }
        actual = hook_wrapper.prepare("path/to/output_dir")
        execute_mock.assert_called_once_with(
            "prepare",
            {
                "IACProjectPath": "path/to/cwd",
                "OutputDirPath": "path/to/output_dir",
                "Debug": False,
            },
        )
        self.assertEqual(actual, "path/to/metadata")

    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._execute")
    def test_prepare_fail(self, execute_mock, load_hook_package_mock):
        hook_wrapper = IacHookWrapper("test_id")
        execute_mock.return_value = {
            "Header": {},
        }
        with self.assertRaises(InvalidHookWrapperException) as e:
            hook_wrapper.prepare("path/to/iac_project", "path/to/output_dir", True, "path/to/log_file")

        self.assertEqual(e.exception.message, "Metadata file path not found in the prepare hook output")


class TestExecuteAsModule(TestCase):
    @patch("samcli.lib.hook.hook_wrapper.importlib.import_module")
    def test_happy_path(self, import_module_mock):
        def my_method(params):
            params["foo"] = "bar"
            return params

        module_mock = Mock()
        method_mock = Mock()
        method_mock.side_effect = my_method
        module_mock.my_method = method_mock
        import_module_mock.return_value = module_mock

        actual = _execute_as_module("my_module", "my_method", {"param1": "value1"})
        self.assertEqual(actual, {"foo": "bar", "param1": "value1"})

    def test_import_error(self):
        with self.assertRaises(InvalidHookWrapperException) as e:
            _execute_as_module("x.y.z", "my_method")

        self.assertEqual(e.exception.message, 'Import error - HookFunctionality module "x.y.z"')

    @patch("samcli.lib.hook.hook_wrapper.importlib.import_module")
    @patch("samcli.lib.hook.hook_wrapper.hasattr")
    def test_no_such_method(self, hasattr_mock, import_module_mock):
        hasattr_mock.return_value = False

        with self.assertRaises(InvalidHookWrapperException) as e:
            _execute_as_module("x.y.z", "my_method")

        self.assertEqual(e.exception.message, 'HookFunctionality module "x.y.z" has no method "my_method"')
