from unittest import TestCase
from unittest.mock import MagicMock, patch, Mock
import os

import click

from samcli.commands._utils.custom_options.hook_name_option import HookNameOption, record_hook_telemetry
from samcli.lib.hook.exceptions import InvalidHookWrapperException


class TestHookPackageIdOption(TestCase):
    def setUp(self):
        self.name = "hook-name"
        self.opt = "--hook-name"
        self.terraform = "terraform"
        self.invalid_coexist_options = ["t", "template", "template-file", "parameters-override"]
        self.metadata_path = "path/metadata.json"
        self.cwd_path = "path/current"

        self.iac_hook_wrapper_instance_mock = MagicMock()
        self.iac_hook_wrapper_instance_mock.prepare.return_value = self.metadata_path

    @patch("samcli.commands._utils.custom_options.hook_name_option.get_available_hook_packages_ids")
    @patch("samcli.lib.hook.hook_wrapper.IacHookWrapper._load_hook_package")
    def test_invalid_hook_name(self, load_hook_package_mock, get_available_hook_packages_ids_mock):
        hook_name = "not_supported"
        available_hook_packages = ["terraform", "cdk"]
        load_hook_package_mock.side_effect = InvalidHookWrapperException(
            f'Cannot locate hook package with hook_name "{hook_name}"'
        )
        get_available_hook_packages_ids_mock.return_value = available_hook_packages

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=[],
        )
        ctx = MagicMock()
        ctx.command.name = "invoke"
        opts = {"hook_name": hook_name}
        args = []
        with self.assertRaises(click.BadParameter) as e:
            hook_name_option.handle_parse_result(ctx, opts, args)

        self.assertEqual(
            e.exception.message,
            f"{hook_name} is not a valid hook name." f"{os.linesep}valid package ids: {available_hook_packages}",
        )

    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_invalid_coexist_options(self, iac_hook_wrapper_mock):
        iac_hook_wrapper_instance_mock = MagicMock()
        iac_hook_wrapper_mock.return_value = iac_hook_wrapper_instance_mock

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        opts = {"hook_name": self.terraform, "template_file": "any/path/template.yaml"}
        args = []
        with self.assertRaises(click.BadParameter) as e:
            hook_name_option.handle_parse_result(ctx, opts, args)

        self.assertEqual(
            e.exception.message,
            f"Parameters hook-name, and {','.join(self.invalid_coexist_options)} cannot be used together",
        )

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_hook_package_with_only_hook_id_option(
        self, iac_hook_wrapper_mock, getcwd_mock, record_hook_telemetry_mock
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=True,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        opts = {
            "hook_name": self.terraform,
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            False,
            None,
            None,
            False,
            None,
            None,
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_hook_package_with_other_options(
        self, iac_hook_wrapper_mock, getcwd_mock, record_hook_telemetry_mock
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=True,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        opts = {
            "hook_name": self.terraform,
            "debug": True,
            "profile": "test",
            "region": "us-east-1",
            "terraform_project_root_path": "/path/path",
            "skip_prepare_infra": True,
            "terraform_plan_file": "/path/plan/file",
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            True,
            "test",
            "us-east-1",
            True,
            "/path/plan/file",
            "/path/path",
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)
        record_hook_telemetry_mock.assert_called_once()

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_skips_hook_package_with_help_option(
        self,
        iac_hook_wrapper_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock
        getcwd_mock.return_value = self.cwd_path

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=True,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        opts = {
            "hook_name": self.terraform,
            "help": True,
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_not_called()
        record_hook_telemetry_mock.assert_not_called()

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_hook_package_with_other_options_from_sam_config(
        self, iac_hook_wrapper_mock, getcwd_mock, record_hook_telemetry_mock
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=True,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {
            "hook_name": self.terraform,
            "debug": True,
            "profile": "test",
            "region": "us-east-1",
            "terraform_project_root_path": "/path/path",
            "skip_prepare_infra": True,
            "terraform_plan_file": "/path/plan/file",
        }
        opts = {}
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            True,
            "test",
            "us-east-1",
            True,
            "/path/plan/file",
            "/path/path",
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_hook_package_with_skipping_prepare_hook_and_built_path_exists(
        self,
        iac_hook_wrapper_mock,
        path_exists_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        path_exists_mock.return_value = True

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        opts = {
            "hook_name": self.terraform,
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_not_called()
        self.assertEqual(opts.get("template_file"), None)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_hook_package_with_skipping_prepare_hook_and_built_path_does_not_exist(
        self,
        iac_hook_wrapper_mock,
        path_exists_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        path_exists_mock.return_value = False

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        opts = {
            "hook_name": self.terraform,
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            False,
            None,
            None,
            False,
            None,
            None,
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_hook_package_with_use_container_and_build_image(
        self,
        iac_hook_wrapper_mock,
        path_exists_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        path_exists_mock.return_value = False

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        ctx.command.name = "build"
        opts = {
            "hook_name": self.terraform,
            "use_container": True,
            "build_image": "image",
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            False,
            None,
            None,
            False,
            None,
            None,
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_invalid_hook_package_with_use_container_and_no_build_image(
        self,
        iac_hook_wrapper_mock,
        path_exists_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        path_exists_mock.return_value = False

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.command.name = "build"
        opts = {
            "hook_name": self.terraform,
            "use_container": True,
        }
        args = []
        with self.assertRaisesRegex(
            click.UsageError,
            "Missing required parameter --build-image.",
        ):
            hook_name_option.handle_parse_result(ctx, opts, args)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_invalid_parameter_hook_with_invalid_project_root_directory(
        self,
        iac_hook_wrapper_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.command.name = "build"
        opts = {
            "hook_name": self.terraform,
            "terraform_project_root_path": "/abs/path",
        }

        args = []
        with self.assertRaisesRegex(
            click.UsageError,
            "/abs/path is not a valid value for Terraform Project Root Path. It should be a parent of "
            "the current directory that contains the root module of the terraform project.",
        ):
            hook_name_option.handle_parse_result(ctx, opts, args)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.isabs")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_parameter_hook_with_valid_absolute_project_root_directory(
        self,
        iac_hook_wrapper_mock,
        path_isabs_mock,
        path_exists_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        path_isabs_mock.return_value = True
        path_exists_mock.return_value = False

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        ctx.command.name = "build"
        opts = {
            "hook_name": self.terraform,
            "terraform_project_root_path": "path",
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            False,
            None,
            None,
            False,
            None,
            "path",
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.isabs")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_parameter_hook_with_valid_relative_project_root_directory(
        self,
        iac_hook_wrapper_mock,
        path_isabs_mock,
        path_exists_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        path_isabs_mock.return_value = False
        path_exists_mock.return_value = False

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        ctx.command.name = "build"
        opts = {
            "hook_name": self.terraform,
            "terraform_project_root_path": "./..",
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            False,
            None,
            None,
            False,
            None,
            "./..",
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_name_option.record_hook_telemetry")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.getcwd")
    @patch("samcli.commands._utils.custom_options.hook_name_option.os.path.exists")
    @patch("samcli.commands._utils.custom_options.hook_name_option.IacHookWrapper")
    def test_valid_hook_package_with_use_container_false_and_no_build_image(
        self,
        iac_hook_wrapper_mock,
        path_exists_mock,
        getcwd_mock,
        record_hook_telemetry_mock,
    ):
        iac_hook_wrapper_mock.return_value = self.iac_hook_wrapper_instance_mock

        getcwd_mock.return_value = self.cwd_path

        path_exists_mock.return_value = False

        hook_name_option = HookNameOption(
            param_decls=(self.name, self.opt),
            force_prepare=False,
            invalid_coexist_options=self.invalid_coexist_options,
        )
        ctx = MagicMock()
        ctx.default_map = {}
        ctx.command.name = "build"
        opts = {
            "hook_name": self.terraform,
            "use_container": False,
        }
        args = []
        hook_name_option.handle_parse_result(ctx, opts, args)
        self.iac_hook_wrapper_instance_mock.prepare.assert_called_once_with(
            os.path.join(self.cwd_path, ".aws-sam-iacs", "iacs_metadata"),
            self.cwd_path,
            False,
            None,
            None,
            False,
            None,
            None,
        )
        self.assertEqual(opts.get("template_file"), self.metadata_path)

    @patch("samcli.commands._utils.custom_options.hook_name_option.EventTracker")
    def test_record_hook_telemetry(self, event_tracker_mock):
        opts = {"terraform_plan_file": "my_plan.json"}
        record_hook_telemetry(opts, Mock())
        event_tracker_mock.track_event.assert_called_once_with("HookConfigurationsUsed", "TerraformPlanFile")
