"""Test Terraform prepare hook"""
from subprocess import CalledProcessError
from unittest.mock import Mock, call, patch, MagicMock
from parameterized import parameterized

from tests.unit.hook_packages.terraform.hooks.prepare.prepare_base import PrepareHookUnitBase

from samcli.hook_packages.terraform.hooks.prepare.hook import prepare, _update_resources_paths
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.subprocess_utils import LoadingPatternError


class TestPrepareHook(PrepareHookUnitBase):
    def setUp(self):
        super().setUp()

    @parameterized.expand(
        [
            (False, False),
            (False, True),
            (True, False),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._update_resources_paths")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.osutils.tempfile_platform_independent")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare(
        self,
        skip_option,
        path_exists,
        mock_subprocess_run,
        mock_json,
        mock_os,
        named_temporary_file_mock,
        mock_open,
        mock_translate_to_cfn,
        mock_update_resources_paths,
        mock_subprocess_loader,
    ):
        tf_plan_filename = "tf_plan"
        output_dir_path = self.prepare_params.get("OutputDirPath")
        metadata_file_path = f"{output_dir_path}/template.json"
        mock_cfn_dict = MagicMock()
        mock_metadata_file = Mock()
        mock_cfn_dict_resources = Mock()
        mock_cfn_dict.get.return_value = mock_cfn_dict_resources

        mock_path = Mock()
        mock_isabs = Mock()
        mock_path.isabs = mock_isabs
        mock_os.path = mock_path
        mock_isabs.return_value = True

        named_temporary_file_mock.return_value.__enter__.return_value.name = tf_plan_filename
        mock_json.loads.return_value = self.tf_json_with_child_modules_and_s3_source_mapping
        mock_translate_to_cfn.return_value = mock_cfn_dict
        mock_os.path.exists.side_effect = [path_exists, True]
        mock_os.path.join.return_value = metadata_file_path
        mock_open.return_value.__enter__.return_value = mock_metadata_file

        self.prepare_params["SkipPrepareInfra"] = skip_option

        expected_prepare_output_dict = {"iac_applications": {"MainApplication": {"metadata_file": metadata_file_path}}}
        iac_prepare_output = prepare(self.prepare_params)

        mock_subprocess_loader.assert_has_calls(
            [
                call(
                    command_args={
                        "args": ["terraform", "init", "-input=false"],
                        "cwd": "iac/project/path",
                    }
                ),
                call(
                    command_args={
                        "args": ["terraform", "plan", "-out", tf_plan_filename, "-input=false"],
                        "cwd": "iac/project/path",
                    }
                ),
            ]
        )
        mock_subprocess_run.assert_has_calls(
            [
                call(
                    ["terraform", "show", "-json", tf_plan_filename],
                    check=True,
                    capture_output=True,
                    cwd="iac/project/path",
                ),
            ]
        )
        mock_translate_to_cfn.assert_called_once_with(
            self.tf_json_with_child_modules_and_s3_source_mapping, output_dir_path, "iac/project/path"
        )
        mock_json.dump.assert_called_once_with(mock_cfn_dict, mock_metadata_file)
        mock_update_resources_paths.assert_called_once_with(mock_cfn_dict_resources, "iac/project/path")
        self.assertEqual(expected_prepare_output_dict, iac_prepare_output)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook._update_resources_paths")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.translate_to_cfn")
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.osutils.tempfile_platform_independent")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_relative_paths(
        self,
        mock_subprocess_run,
        mock_json,
        mock_os,
        named_temporary_file_mock,
        mock_open,
        mock_translate_to_cfn,
        mock_update_resources_paths,
        mock_subprocess_loader,
    ):
        tf_plan_filename = "tf_plan"
        output_dir_path = self.prepare_params.get("OutputDirPath")
        metadata_file_path = f"/current/dir/iac/project/path/{output_dir_path}/template.json"
        mock_cfn_dict = MagicMock()
        mock_metadata_file = Mock()
        mock_cfn_dict_resources = Mock()
        mock_cfn_dict.get.return_value = mock_cfn_dict_resources

        mock_os.getcwd.return_value = "/current/dir"

        mock_path = Mock()
        mock_isabs = Mock()
        mock_normpath = Mock()
        mock_join = Mock()
        mock_path.isabs = mock_isabs
        mock_path.normpath = mock_normpath
        mock_path.join = mock_join
        mock_os.path = mock_path
        mock_isabs.return_value = False
        mock_join.side_effect = [
            "/current/dir/iac/project/path",
            f"/current/dir/iac/project/path/{output_dir_path}",
            f"/current/dir/iac/project/path/{output_dir_path}/template.json",
        ]
        mock_normpath.side_effect = [
            "/current/dir/iac/project/path",
            f"/current/dir/iac/project/path/{output_dir_path}",
        ]

        named_temporary_file_mock.return_value.__enter__.return_value.name = tf_plan_filename
        mock_json.loads.return_value = self.tf_json_with_child_modules_and_s3_source_mapping
        mock_translate_to_cfn.return_value = mock_cfn_dict
        mock_os.path.exists.return_value = True
        mock_os.path.join.return_value = metadata_file_path
        mock_open.return_value.__enter__.return_value = mock_metadata_file

        expected_prepare_output_dict = {"iac_applications": {"MainApplication": {"metadata_file": metadata_file_path}}}
        iac_prepare_output = prepare(self.prepare_params)

        mock_subprocess_loader.assert_has_calls(
            [
                call(
                    command_args={
                        "args": ["terraform", "init", "-input=false"],
                        "cwd": "/current/dir/iac/project/path",
                    }
                ),
                call(
                    command_args={
                        "args": ["terraform", "plan", "-out", tf_plan_filename, "-input=false"],
                        "cwd": "/current/dir/iac/project/path",
                    }
                ),
            ]
        )
        mock_subprocess_run.assert_has_calls(
            [
                call(
                    ["terraform", "show", "-json", tf_plan_filename],
                    check=True,
                    capture_output=True,
                    cwd="/current/dir/iac/project/path",
                ),
            ]
        )
        mock_translate_to_cfn.assert_called_once_with(
            self.tf_json_with_child_modules_and_s3_source_mapping,
            f"/current/dir/iac/project/path/{output_dir_path}",
            "/current/dir/iac/project/path",
        )
        mock_json.dump.assert_called_once_with(mock_cfn_dict, mock_metadata_file)
        mock_update_resources_paths.assert_called_once_with(mock_cfn_dict_resources, "/current/dir/iac/project/path")
        self.assertEqual(expected_prepare_output_dict, iac_prepare_output)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_called_process_error(self, mock_subprocess_run, mock_subprocess_loader):
        mock_subprocess_run.side_effect = CalledProcessError(-2, "terraform init")
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_loader_error(self, mock_subprocess_run, mock_subprocess_loader):
        mock_subprocess_loader.side_effect = LoadingPatternError("Error occurred calling a subprocess")
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.invoke_subprocess_with_loading_pattern")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.translate_to_cfn")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.osutils.tempfile_platform_independent")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.json")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_prepare_with_os_error(
        self,
        mock_subprocess_run,
        mock_json,
        mock_os,
        named_temporary_file_mock,
        mock_translate_to_cfn,
        mock_subprocess_loader,
    ):
        mock_os.path.exists.return_value = False
        mock_os.makedirs.side_effect = OSError()
        with self.assertRaises(PrepareHookException):
            prepare(self.prepare_params)

    def test_prepare_with_no_output_dir_path(self):
        with self.assertRaises(PrepareHookException, msg="OutputDirPath was not supplied"):
            prepare({})

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.Path")
    def test_update_resources_paths(self, mock_path, mock_os):
        abs_path = "/abs/path/value"
        relative_path = "relative/path/value"
        terraform_application_root = "/path/terraform/app/root"

        def side_effect_func(value):
            return value == abs_path

        mock_os.path.isabs = MagicMock(side_effect=side_effect_func)
        updated_relative_path = f"{terraform_application_root}/{relative_path}"
        mock_path_init = Mock()
        mock_path.return_value = mock_path_init
        mock_path_init.joinpath.return_value = updated_relative_path
        resources = {
            "AbsResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": abs_path, "Timeout": 10, "Handler": "app.func"},
            },
            "S3Resource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "Timeout": 10,
                    "Handler": "app.func",
                },
            },
            "RelativeResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": relative_path, "Timeout": 10, "Handler": "app.func"},
            },
            "S3Layer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
            },
            "LayerRelativePath": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": relative_path,
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
            },
            "OtherResource1": {
                "Type": "AWS::Lambda::NotFunction",
                "Properties": {"Code": relative_path, "Timeout": 10, "Handler": "app.func"},
            },
        }
        expected_resources = {
            "AbsResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": abs_path, "Timeout": 10, "Handler": "app.func"},
            },
            "S3Resource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "Timeout": 10,
                    "Handler": "app.func",
                },
            },
            "RelativeResource1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": updated_relative_path, "Timeout": 10, "Handler": "app.func"},
            },
            "S3Layer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": {
                        "S3Bucket": "s3_bucket_name",
                        "S3Key": "s3_key_name",
                    },
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
            },
            "LayerRelativePath": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": updated_relative_path,
                    "CompatibleRuntimes": ["nodejs14.x", "nodejs16.x"],
                    "CompatibleArchitectures": ["arm64"],
                },
            },
            "OtherResource1": {
                "Type": "AWS::Lambda::NotFunction",
                "Properties": {"Code": relative_path, "Timeout": 10, "Handler": "app.func"},
            },
        }
        _update_resources_paths(resources, terraform_application_root)
        self.assertDictEqual(resources, expected_resources)

    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.os")
    @patch("samcli.hook_packages.terraform.hooks.prepare.hook.run")
    def test_skip_prepare_infra_with_metadata_file(self, run_mock, os_mock):
        os_path_join = Mock()
        os_mock.path.join = os_path_join
        os_mock.path.exists.return_value = True

        self.prepare_params["SkipPrepareInfra"] = True

        prepare(self.prepare_params)

        run_mock.assert_not_called()
