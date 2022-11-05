"""Test Hook Warpper"""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.lib.hook.hook_wrapper import IacHookWrapper, _execute_as_module, get_available_hook_packages_ids
from samcli.lib.hook.exceptions import (
    InvalidHookWrapperException,
    InvalidHookPackageConfigException,
    HookPackageExecuteFunctionalityException,
)

TEST_HOOK_PACKAGE_CONFIG = {
    "hook_name": "my_test_hook_name",
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
    @patch("samcli.lib.hook.hook_wrapper.INTERNAL_PACKAGES_ROOT")
    def test_instantiate_success(self, INTERNAL_PACKAGES_ROOT_MOCK, HookPackageConfigMock):
        INTERNAL_PACKAGES_ROOT_MOCK.iterdir.return_value = [
            Path("path/to/hook_package_1"),
            Path("path/to/hook_package_2"),
            Path("path/to/hook_package_3"),
        ]
        hook_package_1_config_mock = Mock()
        hook_package_2_config_mock = Mock()
        hook_package_3_config_mock = Mock()

        HookPackageConfigMock.return_value = hook_package_3_config_mock

        hook_package = IacHookWrapper("hook_package_3")
        self.assertEqual(hook_package._config, hook_package_3_config_mock)

    @patch("samcli.lib.hook.hook_wrapper.INTERNAL_PACKAGES_ROOT")
    def test_instantiate_package_not_found(self, INTERNAL_PACKAGES_ROOT_MOCK):
        INTERNAL_PACKAGES_ROOT_MOCK.iterdir.return_value = [
            Path("path/to/hook_package_1"),
            Path("path/to/hook_package_2"),
            Path("path/to/hook_package_3"),
        ]

        with self.assertRaises(InvalidHookWrapperException) as e:
            IacHookWrapper("hook_package_4")

        self.assertEqual(e.exception.message, 'Cannot locate hook package with hook_name "hook_package_4"')

    @patch("samcli.lib.hook.hook_wrapper.HookPackageConfig")
    @patch("samcli.lib.hook.hook_wrapper.INTERNAL_PACKAGES_ROOT")
    def test_instantiate_fail_with_invalid_config(self, INTERNAL_PACKAGES_ROOT_MOCK, HookPackageConfigMock):
        INTERNAL_PACKAGES_ROOT_MOCK.iterdir.return_value = [
            Path("path/to/hook_package_1"),
            Path("path/to/hook_package_2"),
            Path("path/to/hook_package_3"),
        ]

        HookPackageConfigMock.side_effect = InvalidHookPackageConfigException("Invalid config")

        with self.assertRaises(InvalidHookPackageConfigException) as e:
            IacHookWrapper("hook_package_3")

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
            "iac_applications": {
                "MainApplication": {
                    "metadata_file": "path/to/metadata",
                },
            },
        }
        actual = hook_wrapper.prepare("path/to/output_dir", "path/to/iac_project", True, "my_profile", "us-east-1")
        execute_mock.assert_called_once_with(
            "prepare",
            {
                "IACProjectPath": "path/to/iac_project",
                "OutputDirPath": "path/to/output_dir",
                "Debug": True,
                "Profile": "my_profile",
                "Region": "us-east-1",
                "SkipPrepareInfra": False,
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
            "header": {},
            "iac_applications": {
                "MainApplication": {
                    "metadata_file": "path/to/metadata",
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
                "SkipPrepareInfra": False,
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
            hook_wrapper.prepare("path/to/iac_project", "path/to/output_dir", True)

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


class TestGetAvailableHookPackagesIds(TestCase):
    @patch("samcli.lib.hook.hook_wrapper.INTERNAL_PACKAGES_ROOT")
    def test_get_available_hook_pacakges(self, INTERNAL_PACKAGES_ROOT_MOCK):
        path1_mock = Mock()
        path1_mock.name = "hook_package_1"
        path1_mock.is_dir.return_value = True

        path2_mock = Mock()
        path2_mock.name = "hook_package_2"
        path2_mock.is_dir.return_value = True

        path3_mock = Mock()
        path3_mock.name = "hook_package_3"
        path3_mock.is_dir.return_value = False

        INTERNAL_PACKAGES_ROOT_MOCK.iterdir.return_value = [
            path1_mock,
            path2_mock,
            path3_mock,
        ]
        self.assertEqual(get_available_hook_packages_ids(), ["hook_package_1", "hook_package_2"])
