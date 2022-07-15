from unittest import TestCase
from unittest.mock import MagicMock, patch
import os

import click

from samcli.commands._utils.custom_options.hook_package_id_option import HookPackageIdOption
from samcli.lib.hook.exceptions import InvalidHookWrapperException


class TestHookPackageIdOption(TestCase):
    def setUp(self):
        self.name = "hook-package-id"
        self.opt = "--hook-package-id"

    @patch("samcli.commands._utils.custom_options.hook_package_id_option.get_available_hook_packages_ids")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_invalid_hook_package_id(self, load_hook_package_mock, get_available_hook_packages_ids_mock):
        hook_package_id = "not_supported"
        available_hook_packages = ["terraform", "cdk"]
        load_hook_package_mock.side_effect = InvalidHookWrapperException(
            f'Cannot locate hook package with hook_package_id "{hook_package_id}"'
        )
        get_available_hook_packages_ids_mock.return_value = available_hook_packages

        hook_package_id_option = HookPackageIdOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=[],
        )
        ctx = MagicMock()
        opts = {"hook_package_id": hook_package_id}
        args = []
        with self.assertRaises(click.BadParameter) as e:
            hook_package_id_option.handle_parse_result(ctx, opts, args)

        self.assertEqual(
            e.exception.message,
            f"{hook_package_id} is not a valid hook package id. This is the list of valid "
            f"packages ids {available_hook_packages}",
        )

    @patch("samcli.commands._utils.custom_options.hook_package_id_option.IacHookWrapper")
    def test_invalid_coexist_options(self, iac_hook_wrapper_mock):
        hook_package_id = "terraform"
        invalid_coexist_options = ["t", "template", "template-file", "parameters-override"]
        iac_hook_wrapper_instance_mock = MagicMock()
        iac_hook_wrapper_mock.return_value = iac_hook_wrapper_instance_mock

        hook_package_id_option = HookPackageIdOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=invalid_coexist_options,
        )
        ctx = MagicMock()
        opts = {
            "hook_package_id": hook_package_id,
            "template_file": "any/path/template.yaml"
        }
        args = []
        with self.assertRaises(click.BadParameter) as e:
            hook_package_id_option.handle_parse_result(ctx, opts, args)

        self.assertEqual(
            e.exception.message,
            f"Parameters hook-package-id, and {','.join(invalid_coexist_options)} could not be used together"
        )

    @patch("samcli.commands._utils.custom_options.hook_package_id_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_package_id_option.IacHookWrapper")
    def test_valid_hook_package_with_only_hook_id_option(self, iac_hook_wrapper_mock, getcwd_mock):
        hook_package_id = "terraform"
        metadata_path = "path/metadata.json"
        cwd_path = "path/current"
        invalid_coexist_options = ["t", "template", "template-file", "parameters-override"]

        iac_hook_wrapper_instance_mock = MagicMock()
        iac_hook_wrapper_instance_mock.prepare.return_value = metadata_path
        iac_hook_wrapper_mock.return_value = iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = cwd_path

        hook_package_id_option = HookPackageIdOption(
            param_decls=(self.name, self.opt),
            force_prepare=True,
            invalid_coexist_options=invalid_coexist_options,
        )
        ctx = MagicMock()
        opts = {
            "hook_package_id": hook_package_id,
        }
        args = []
        hook_package_id_option.handle_parse_result(ctx, opts, args)
        iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(".aws-sam", "iacs_metadata"),
            cwd_path,
            False,
            None,
            None
        )
        self.assertEqual(opts.get("template_file"), metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_package_id_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_package_id_option.IacHookWrapper")
    def test_valid_hook_package_with_other_options(self, iac_hook_wrapper_mock, getcwd_mock):
        hook_package_id = "terraform"
        metadata_path = "path/metadata.json"
        cwd_path = "path/current"
        invalid_coexist_options = ["t", "template", "template-file", "parameters-override"]

        iac_hook_wrapper_instance_mock = MagicMock()
        iac_hook_wrapper_instance_mock.prepare.return_value = metadata_path
        iac_hook_wrapper_mock.return_value = iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = cwd_path

        hook_package_id_option = HookPackageIdOption(
            param_decls=(self.name, self.opt),
            force_prepare=True,
            invalid_coexist_options=invalid_coexist_options,
        )
        ctx = MagicMock()
        opts = {
            "hook_package_id": hook_package_id,
            "debug": True,
            "profile": "test",
            "region": "us-east-1",
        }
        args = []
        hook_package_id_option.handle_parse_result(ctx, opts, args)
        iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(".aws-sam", "iacs_metadata"),
            cwd_path,
            True,
            "test",
            "us-east-1",
        )
        self.assertEqual(opts.get("template_file"), metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_package_id_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_package_id_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_package_id_option.IacHookWrapper")
    def test_valid_hook_package_with_skipping_prepare_hook_and_built_path_exists(self, iac_hook_wrapper_mock, path_exists_mock, getcwd_mock):
        hook_package_id = "terraform"
        metadata_path = "path/metadata.json"
        cwd_path = "path/current"
        invalid_coexist_options = ["t", "template", "template-file", "parameters-override"]

        iac_hook_wrapper_instance_mock = MagicMock()
        iac_hook_wrapper_instance_mock.prepare.return_value = metadata_path
        iac_hook_wrapper_mock.return_value = iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = cwd_path

        path_exists_mock.return_value = True

        hook_package_id_option = HookPackageIdOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=invalid_coexist_options,
        )
        ctx = MagicMock()
        opts = {
            "hook_package_id": hook_package_id,
        }
        args = []
        hook_package_id_option.handle_parse_result(ctx, opts, args)
        iac_hook_wrapper_instance_mock.prepare.assert_not_called()
        self.assertEqual(opts.get("template_file"), None)

    @patch("samcli.commands._utils.custom_options.hook_package_id_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_package_id_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_package_id_option.IacHookWrapper")
    def test_valid_hook_package_with_skipping_prepare_hook_and_built_path_doesnot_exist(self, iac_hook_wrapper_mock,
                                                                                 path_exists_mock, getcwd_mock):
        hook_package_id = "terraform"
        metadata_path = "path/metadata.json"
        cwd_path = "path/current"
        invalid_coexist_options = ["t", "template", "template-file", "parameters-override"]

        iac_hook_wrapper_instance_mock = MagicMock()
        iac_hook_wrapper_instance_mock.prepare.return_value = metadata_path
        iac_hook_wrapper_mock.return_value = iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = cwd_path

        path_exists_mock.return_value = False

        hook_package_id_option = HookPackageIdOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=invalid_coexist_options,
        )
        ctx = MagicMock()
        opts = {
            "hook_package_id": hook_package_id,
        }
        args = []
        hook_package_id_option.handle_parse_result(ctx, opts, args)
        iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(".aws-sam", "iacs_metadata"),
            cwd_path,
            False,
            None,
            None
        )
        self.assertEqual(opts.get("template_file"), metadata_path)
