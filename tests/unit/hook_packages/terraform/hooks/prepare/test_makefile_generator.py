"""Test Terraform prepare Makefile"""
from unittest.mock import patch, Mock
from parameterized import parameterized

from tests.unit.hook_packages.terraform.hooks.prepare.prepare_base import PrepareHookUnitBase
from samcli.hook_packages.terraform.hooks.prepare.types import (
    SamMetadataResource,
)
from samcli.hook_packages.terraform.hooks.prepare.makefile_generator import (
    generate_makefile_rule_for_lambda_resource,
    generate_makefile,
    _get_makefile_build_target,
    _get_parent_modules,
    _build_jpath_string,
    _format_makefile_recipe,
    _build_makerule_python_command,
)
from samcli.hook_packages.terraform.hooks.prepare.types import TFResource


class TestPrepareMakefile(PrepareHookUnitBase):
    def setUp(self):
        super().setUp()

    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._get_makefile_build_target")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._format_makefile_recipe")
    def test_generate_makefile_rule_for_lambda_resource(self, format_recipe_mock, get_build_target_mock):
        format_recipe_mock.side_effect = [
            "\tpython3 .aws-sam/iacs_metadata/copy_terraform_built_artifacts.py --expression "
            '"|values|root_module|resources|[?address=="null_resource.sam_metadata_aws_lambda_function"]'
            '|values|triggers|built_output_path" --directory "$(ARTIFACTS_DIR)" '
            '--target "null_resource.sam_metadata_aws_lambda_function"\n',
        ]
        get_build_target_mock.return_value = "build-function_logical_id:\n"
        sam_metadata_resource = SamMetadataResource(
            current_module_address=None,
            resource={"address": "null_resource.sam_metadata_aws_lambda_function"},
            config_resource=TFResource("", "", None, {}),
        )
        makefile_rule = generate_makefile_rule_for_lambda_resource(
            python_command_name="python",
            output_dir="/some/dir/path/.aws-sam/output",
            sam_metadata_resource=sam_metadata_resource,
            terraform_application_dir="/some/dir/path",
            logical_id="function_logical_id",
        )
        expected_makefile_rule = (
            "build-function_logical_id:\n"
            "\tpython3 .aws-sam/iacs_metadata/copy_terraform_built_artifacts.py "
            '--expression "|values|root_module|resources|[?address=="null_resource.sam_metadata_aws_lambda_function"]'
            '|values|triggers|built_output_path" --directory "$(ARTIFACTS_DIR)" '
            '--target "null_resource.sam_metadata_aws_lambda_function"\n'
        )
        self.assertEqual(makefile_rule, expected_makefile_rule)

    @parameterized.expand(
        [
            "null_resource.sam_metadata_aws_lambda_function",
            "null_resource.sam_metadata_aws_lambda_function[2]",
            'null_resource.sam_metadata_aws_lambda_layer_version_layers["layer3"]',
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._build_jpath_string")
    def test_build_makerule_python_command(self, resource, jpath_string_mock):
        jpath_string_mock.return_value = (
            "|values|root_module|resources|" f'[?address=="{resource}"]' "|values|triggers|built_output_path"
        )
        sam_metadata_resource = SamMetadataResource(
            current_module_address=None, resource={}, config_resource=TFResource("", "", None, {})
        )
        show_command = _build_makerule_python_command(
            python_command_name="python",
            output_dir="/some/dir/path/.aws-sam/output",
            resource_address=resource,
            sam_metadata_resource=sam_metadata_resource,
            terraform_application_dir="/some/dir/path",
        )
        script_path = ".aws-sam/output/copy_terraform_built_artifacts.py"
        escaped_resource = resource.replace('"', '\\"')
        expected_show_command = (
            f'python "{script_path}" '
            '--expression "|values|root_module|resources|'
            f'[?address==\\"{escaped_resource}\\"]'
            '|values|triggers|built_output_path" --directory "$(ARTIFACTS_DIR)" '
            f'--target "{escaped_resource}"'
        )
        self.assertEqual(show_command, expected_show_command)

    def test_get_makefile_build_target(self):
        output_string = _get_makefile_build_target("function_logical_id")
        self.assertRegex(output_string, r"^build-function_logical_id:(\n|\r\n)$")

    def test__format_makefile_recipe(self):
        output_string = _format_makefile_recipe("terraform show -json | python3")
        self.assertRegex(output_string, r"^\tterraform show -json \| python3(\n|\r\n)$")

    @parameterized.expand(
        [
            (
                None,
                '|values|root_module|resources|[?address=="null_resource'
                '.sam_metadata_aws_lambda_function"]|values|triggers|built_output_path',
            ),
            (
                "module.level1_lambda",
                "|values|root_module|child_modules|[?address==module.level1_lambda]|resources|"
                '[?address=="null_resource.sam_metadata_aws_lambda_function"]|values|triggers|built_output_path',
            ),
            (
                "module.level1_lambda.module.level2_lambda",
                "|values|root_module|child_modules|[?address==module.level1_lambda]|child_modules|"
                "[?address==module.level1_lambda.module.level2_lambda]|resources|[?address=="
                '"null_resource.sam_metadata_aws_lambda_function"]|values|triggers|built_output_path',
            ),
        ]
    )
    def test_build_jpath_string(self, module_address, expected_jpath):
        sam_metadata_resource = SamMetadataResource(
            current_module_address=module_address, resource={}, config_resource=TFResource("", "", None, {})
        )
        self.assertEqual(
            _build_jpath_string(sam_metadata_resource, "null_resource.sam_metadata_aws_lambda_function"), expected_jpath
        )

    @parameterized.expand(
        [
            (None, []),
            (
                "module.level1_lambda",
                ["module.level1_lambda"],
            ),
            (
                "module.level1_lambda.module.level2_lambda",
                ["module.level1_lambda", "module.level1_lambda.module.level2_lambda"],
            ),
            (
                "module.level1_lambda.module.level2_lambda.module.level3_lambda",
                [
                    "module.level1_lambda",
                    "module.level1_lambda.module.level2_lambda",
                    "module.level1_lambda.module.level2_lambda.module.level3_lambda",
                ],
            ),
        ]
    )
    def test_get_parent_modules(self, module_address, expected_list):
        self.assertEqual(_get_parent_modules(module_address), expected_list)

    @parameterized.expand([(True,), (False,)])
    @patch("builtins.open")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator.shutil")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator.os")
    def test_generate_makefile(
        self,
        output_dir_exists,
        mock_os,
        mock_shutil,
        mock_open,
    ):
        mock_os.path.exists.return_value = output_dir_exists

        mock_copy_tf_backend_override_file_path = Mock()
        mock_copy_terraform_built_artifacts_script_path = Mock()
        mock_makefile_path = Mock()
        mock_os.path.dirname.return_value = ""
        mock_os.path.join.side_effect = [
            mock_copy_tf_backend_override_file_path,
            mock_copy_terraform_built_artifacts_script_path,
            mock_makefile_path,
        ]

        mock_makefile = Mock()
        mock_open.return_value.__enter__.return_value = mock_makefile

        mock_makefile_rules = Mock()
        mock_output_directory_path = Mock()

        generate_makefile(mock_makefile_rules, mock_output_directory_path)

        if output_dir_exists:
            mock_os.makedirs.assert_not_called()
        else:
            mock_os.makedirs.assert_called_once_with(mock_output_directory_path, exist_ok=True)

        mock_shutil.copy.assert_called_once_with(
            mock_copy_terraform_built_artifacts_script_path, mock_output_directory_path
        )

        mock_makefile.writelines.assert_called_once_with(mock_makefile_rules)
