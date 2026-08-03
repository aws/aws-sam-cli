"""Test Terraform prepare Makefile"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest import skipIf
from unittest.mock import patch, Mock, call
from parameterized import parameterized

from tests.testing_utils import IS_WINDOWS
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
    _write_makerule_args_file,
)
from samcli.hook_packages.terraform.hooks.prepare.types import TFResource


class TestPrepareMakefile(PrepareHookUnitBase):
    def setUp(self):
        super().setUp()

    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._get_makefile_build_target")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._format_makefile_recipe")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._write_makerule_args_file")
    def test_generate_makefile_rule_for_lambda_resource(
        self, write_args_file_mock, format_recipe_mock, get_build_target_mock
    ):
        write_args_file_mock.return_value = "/some/dir/path/.aws-sam/output/function_logical_id.args.json"
        format_recipe_mock.side_effect = [
            "\tpython3 .aws-sam/iacs_metadata/copy_terraform_built_artifacts.py "
            '--directory "$(ARTIFACTS_DIR)" '
            '--args-file ".aws-sam/output/function_logical_id.args.json"\n',
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
            '--directory "$(ARTIFACTS_DIR)" '
            '--args-file ".aws-sam/output/function_logical_id.args.json"\n'
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
        jpath_string = "|values|root_module|resources|" f'[?address=="{resource}"]' "|values|triggers|built_output_path"
        jpath_string_mock.return_value = jpath_string
        sam_metadata_resource = SamMetadataResource(
            current_module_address=None, resource={}, config_resource=TFResource("", "", None, {})
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            terraform_application_dir = os.path.join(tmpdir, "some", "dir", "path")
            output_dir = os.path.join(terraform_application_dir, ".aws-sam", "output")
            os.makedirs(output_dir)

            show_command = _build_makerule_python_command(
                python_command_name="python",
                output_dir=output_dir,
                resource_address=resource,
                sam_metadata_resource=sam_metadata_resource,
                terraform_application_dir=terraform_application_dir,
                logical_id="function_logical_id",
            )

            script_path = ".aws-sam/output/copy_terraform_built_artifacts.py"
            self.assertIn(f'python "{script_path}"', show_command)
            self.assertIn('--directory "$(ARTIFACTS_DIR)"', show_command)
            self.assertIn("--args-file", show_command)

            # the args file path referenced in the recipe should point to a real file
            # containing the expression/target values, written under output_dir
            args_file_relative_path = show_command.split("--args-file")[1].strip().strip('"')
            args_file_path = os.path.join(terraform_application_dir, args_file_relative_path)
            self.assertTrue(os.path.exists(args_file_path))
            with open(args_file_path) as f:
                args_file_contents = json.load(f)
            self.assertEqual(args_file_contents, {"expression": jpath_string, "target": resource})

    def test_write_makerule_args_file_round_trips_arbitrary_values(self):
        # Values written to the args file must come back byte-for-byte identical when read back
        # as JSON, including values that were previously dangerous when embedded directly in a
        # shell command line (backticks, $(...), embedded newlines, quotes, etc). JSON encoding
        # neutralizes all of these without needing any shell- or make-specific escaping, because
        # the value is never parsed as code - only ever as a JSON string.
        malicious_values = [
            'null_resource.sam_metadata["normal`touch /tmp/poc_sam_rce`"]',
            'null_resource.sam_metadata["normal$(touch /tmp/poc_sam_rce)"]',
            'null_resource.sam_metadata["normal${IFS}touch${IFS}/tmp/poc_sam_rce"]',
            'null_resource.sam_metadata["normal" && touch /tmp/poc_sam_rce && echo "]',
            'null_resource.sam_metadata["normal\ntouch /tmp/poc_sam_rce"]',
            'null_resource.sam_metadata["normal\r\ntouch /tmp/poc_sam_rce"]',
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            for malicious_value in malicious_values:
                args_file_path = _write_makerule_args_file(
                    tmpdir, "function_logical_id", malicious_value, malicious_value
                )
                with open(args_file_path) as f:
                    contents = json.load(f)
                self.assertEqual(contents, {"expression": malicious_value, "target": malicious_value})

    def test_write_makerule_args_file_uses_deterministic_name_and_overwrites(self):
        # The args file name must be deterministic (derived only from logical_id, no random
        # component) so that re-running `sam build` (which always re-runs prepare) overwrites
        # the previous run's file for this resource instead of accumulating a new file on disk
        # on every build.
        with tempfile.TemporaryDirectory() as tmpdir:
            first_path = _write_makerule_args_file(tmpdir, "function_logical_id", "expr-1", "target-1")
            second_path = _write_makerule_args_file(tmpdir, "function_logical_id", "expr-2", "target-2")

            self.assertEqual(first_path, second_path)
            self.assertEqual(os.path.basename(first_path), "function_logical_id.args.json")
            self.assertEqual(len(os.listdir(tmpdir)), 1)

            with open(second_path) as f:
                contents = json.load(f)
            self.assertEqual(contents, {"expression": "expr-2", "target": "target-2"})

    def test_write_makerule_args_file_creates_output_dir_if_missing(self):
        # _write_makerule_args_file can run before generate_makefile() has had a chance to
        # create output_dir (the prepare-hook contract does not guarantee the directory
        # pre-exists - see hook.py's prepare(), which creates it itself rather than assuming
        # the caller did). It must not rely on a directory created elsewhere.
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "does", "not", "exist", "yet")
            self.assertFalse(os.path.exists(output_dir))

            args_file_path = _write_makerule_args_file(output_dir, "function_logical_id", "expr", "target")

            self.assertTrue(os.path.exists(args_file_path))
            with open(args_file_path) as f:
                contents = json.load(f)
            self.assertEqual(contents, {"expression": "expr", "target": "target"})

    @parameterized.expand(
        [
            (
                # backtick command substitution in a for_each key must not be shell-executed
                'null_resource.sam_metadata["normal`touch {marker}`"]',
            ),
            (
                # $() command substitution in a for_each key must not be shell-executed
                'null_resource.sam_metadata["normal$(touch {marker})"]',
            ),
            (
                # ${...} shell parameter expansion must not be shell-executed
                'null_resource.sam_metadata["normal${{IFS}}touch${{IFS}}{marker}"]',
            ),
            (
                # double quote injection must not break out of the recipe argument
                'null_resource.sam_metadata["normal" ; touch {marker} ; echo "]',
            ),
            (
                # embedded newline must not split the recipe into multiple physical lines
                'null_resource.sam_metadata["normal\ntouch {marker}"]',
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._build_jpath_string")
    def test_build_makerule_python_command_keeps_untrusted_values_off_the_command_line(
        self, malicious_resource_template, jpath_string_mock
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a per-test unique marker path so this test can't collide with a stale file
            # left by another process or a parallel test worker, and doesn't depend on any
            # pre-existing state under /tmp.
            marker_path = os.path.join(tmpdir, "poc_sam_rce")
            malicious_resource = malicious_resource_template.format(marker=marker_path)
            malicious_jpath = (
                "|values|root_module|resources|"
                f'[?address=="{malicious_resource}"]'
                "|values|triggers|built_output_path"
            )
            jpath_string_mock.return_value = malicious_jpath

            terraform_application_dir = os.path.join(tmpdir, "some", "dir", "path")
            output_dir = os.path.join(terraform_application_dir, ".aws-sam", "output")
            os.makedirs(output_dir)

            sam_metadata_resource = SamMetadataResource(
                current_module_address=None, resource={}, config_resource=TFResource("", "", None, {})
            )
            show_command = _build_makerule_python_command(
                python_command_name="python",
                output_dir=output_dir,
                resource_address=malicious_resource,
                sam_metadata_resource=sam_metadata_resource,
                terraform_application_dir=terraform_application_dir,
                logical_id="function_logical_id",
            )

            # Structural guarantee: the untrusted resource address/expression must never appear
            # in the recipe text at all - only a SAM-CLI-generated file path may appear there.
            self.assertNotIn(malicious_resource, show_command)
            self.assertNotIn(malicious_jpath, show_command)
            self.assertNotIn("\n", show_command)

            # Behavioral guarantee: actually executing the recipe (as make would, handing it to
            # a shell after its own macro expansion) must not run the injected command, since
            # the untrusted value never reaches the shell in the first place.
            if not IS_WINDOWS:
                shell_command = show_command.replace("$$", "$")
                subprocess.run(["sh", "-c", shell_command], capture_output=True, text=True)
                self.assertFalse(
                    os.path.exists(marker_path),
                    f"Command injection succeeded for payload: {malicious_resource!r}",
                )

            # The untrusted value must still reach the args file untouched, so the legitimate
            # (non-injection) behavior of building this resource is preserved.
            args_file_relative_path = show_command.split("--args-file")[1].strip().strip('"')
            args_file_path = os.path.join(terraform_application_dir, args_file_relative_path)
            with open(args_file_path) as f:
                args_file_contents = json.load(f)
            self.assertEqual(args_file_contents, {"expression": malicious_jpath, "target": malicious_resource})

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
        mock_zip_module_path = Mock()
        mock_makefile_path = Mock()
        mock_os.path.dirname.return_value = ""
        mock_os.path.join.side_effect = [
            mock_copy_tf_backend_override_file_path,
            mock_copy_terraform_built_artifacts_script_path,
            mock_zip_module_path,
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

        mock_shutil.copy.assert_has_calls(
            [
                call(mock_copy_terraform_built_artifacts_script_path, mock_output_directory_path),
                call(mock_zip_module_path, mock_output_directory_path),
            ]
        )
        mock_makefile.writelines.assert_called_once_with(mock_makefile_rules)
