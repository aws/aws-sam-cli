"""Test Terraform prepare Makefile"""

import json
import os
import subprocess
import tempfile
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
    _get_args_file_path,
    PendingArgsFile,
    ARGS_FILE_NAME_HASH_LEN,
)
from samcli.hook_packages.terraform.hooks.prepare.types import TFResource


class TestPrepareMakefile(PrepareHookUnitBase):
    def setUp(self):
        super().setUp()

    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._get_makefile_build_target")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._format_makefile_recipe")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator._build_makerule_python_command")
    def test_generate_makefile_rule_for_lambda_resource(
        self, build_command_mock, format_recipe_mock, get_build_target_mock
    ):
        pending_args_file = PendingArgsFile(
            path="/some/dir/path/.aws-sam/output/deadbeefdeadbeef.args.json",
            expression="some-expression",
            target="null_resource.sam_metadata_aws_lambda_function",
        )
        build_command_mock.return_value = (
            'python3 ".aws-sam/iacs_metadata/copy_terraform_built_artifacts.py" '
            '--directory "$(ARTIFACTS_DIR)" --args-file ".aws-sam/output/deadbeefdeadbeef.args.json"',
            pending_args_file,
        )
        format_recipe_mock.side_effect = [
            "\tpython3 .aws-sam/iacs_metadata/copy_terraform_built_artifacts.py "
            '--directory "$(ARTIFACTS_DIR)" '
            '--args-file ".aws-sam/output/deadbeefdeadbeef.args.json"\n',
        ]
        get_build_target_mock.return_value = "build-function_logical_id:\n"
        sam_metadata_resource = SamMetadataResource(
            current_module_address=None,
            resource={"address": "null_resource.sam_metadata_aws_lambda_function"},
            config_resource=TFResource("", "", None, {}),
        )
        makefile_rule, returned_pending_args_file = generate_makefile_rule_for_lambda_resource(
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
            '--args-file ".aws-sam/output/deadbeefdeadbeef.args.json"\n'
        )
        self.assertEqual(makefile_rule, expected_makefile_rule)
        # generate_makefile_rule_for_lambda_resource performs no I/O of its own; it just passes
        # the PendingArgsFile through from _build_makerule_python_command for the caller to
        # collect and hand to generate_makefile() once every rule has been built successfully.
        self.assertEqual(returned_pending_args_file, pending_args_file)

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
        terraform_application_dir = os.path.join("some", "dir", "path")
        output_dir = os.path.join(terraform_application_dir, ".aws-sam", "output")

        # _build_makerule_python_command is a pure function - it performs no I/O and can be
        # tested without a real filesystem: the args file it references is only described by
        # the returned PendingArgsFile, not written to disk here.
        show_command, pending_args_file = _build_makerule_python_command(
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

        # the args file path referenced in the recipe should match the PendingArgsFile's path,
        # and the PendingArgsFile should carry the expression/target this rule needs
        args_file_relative_path = show_command.split("--args-file")[1].strip().strip('"')
        args_file_path = os.path.join(terraform_application_dir, args_file_relative_path)
        self.assertEqual(pending_args_file.path, args_file_path)
        self.assertEqual(pending_args_file.expression, jpath_string)
        self.assertEqual(pending_args_file.target, resource)

    def test_get_args_file_path_is_deterministic_and_pure(self):
        # _get_args_file_path must be a pure function of its inputs - same logical_id, same
        # output_dir, same path, every time, with no filesystem access - so that
        # _build_makerule_python_command (and generate_makefile_rule_for_lambda_resource above
        # it) can remain pure as well. Writing anything to disk is deferred entirely to
        # generate_makefile(), once every rule has been built successfully.
        first_path = _get_args_file_path("/some/dir/path/.aws-sam/output", "function_logical_id")
        second_path = _get_args_file_path("/some/dir/path/.aws-sam/output", "function_logical_id")
        self.assertEqual(first_path, second_path)
        self.assertTrue(os.path.basename(first_path).endswith(".args.json"))

    def test_get_args_file_path_keeps_file_name_short_regardless_of_logical_id(self):
        # The args file is named by hashing logical_id to a fixed-length string, rather than
        # embedding (even truncated) logical_id itself. logical_id can be up to 255 *characters*
        # and is Unicode-aware ("alphanumeric" is not limited to ASCII - see
        # build_cfn_logical_id()), so a truncation-based name would have to reason separately
        # about the 255-*byte* per-component filesystem/OS filename limit and, on Windows, the
        # 260-character MAX_PATH limit on the *total* path (which a real project path can push
        # past well before the per-component limit, since it counts the project's own path
        # depth too). A fixed-length hash sidesteps both regardless of how long or non-ASCII
        # logical_id is: this asserts the file name is always the same short length for a
        # maximally long ASCII logical_id, a maximally long non-ASCII (CJK) logical_id, and a
        # short one alike.
        logical_ids = [
            "A" * 255,  # maximally long ASCII logical_id
            "\u9577" * 255,  # maximally long CJK logical_id (3 bytes each in UTF-8 = 765 bytes)
            "function_logical_id",  # a typical short logical_id
        ]
        output_dir = os.path.join("some", "dir", "path", ".aws-sam", "output")
        file_names = set()
        for logical_id in logical_ids:
            args_file_path = _get_args_file_path(output_dir, logical_id)
            file_name = os.path.basename(args_file_path)
            file_names.add(file_name)
            self.assertEqual(len(file_name), ARGS_FILE_NAME_HASH_LEN + len(".args.json"))
        # each distinct logical_id must still map to a distinct file
        self.assertEqual(len(file_names), len(logical_ids))

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

            sam_metadata_resource = SamMetadataResource(
                current_module_address=None, resource={}, config_resource=TFResource("", "", None, {})
            )
            show_command, pending_args_file = _build_makerule_python_command(
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
            # the untrusted value never reaches the shell in the first place. This function no
            # longer writes the args file itself (that's deferred to generate_makefile()), but
            # the recipe text is identical either way, so this remains a faithful test of what
            # `make` would actually hand to a shell.
            if not IS_WINDOWS:
                shell_command = show_command.replace("$$", "$")
                subprocess.run(["sh", "-c", shell_command], capture_output=True, text=True)
                self.assertFalse(
                    os.path.exists(marker_path),
                    f"Command injection succeeded for payload: {malicious_resource!r}",
                )

            # The untrusted value must still reach the PendingArgsFile untouched, so the
            # legitimate (non-injection) behavior of building this resource is preserved.
            self.assertEqual(pending_args_file.expression, malicious_jpath)
            self.assertEqual(pending_args_file.target, malicious_resource)

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
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator.glob")
    @patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator.os")
    def test_generate_makefile(
        self,
        output_dir_exists,
        mock_os,
        mock_glob,
        mock_shutil,
        mock_open,
    ):
        mock_os.path.exists.return_value = output_dir_exists
        mock_glob.glob.return_value = []

        mock_copy_tf_backend_override_file_path = Mock()
        mock_copy_terraform_built_artifacts_script_path = Mock()
        mock_zip_module_path = Mock()
        mock_makefile_path = Mock()
        mock_os.path.dirname.return_value = ""
        mock_os.path.join.side_effect = [
            "/output/dir/*.args.json",  # glob pattern for pruning stale args files
            mock_copy_tf_backend_override_file_path,
            mock_copy_terraform_built_artifacts_script_path,
            mock_zip_module_path,
            mock_makefile_path,
        ]

        mock_makefile = Mock()
        mock_args_file = Mock()
        mock_backend_override_file = Mock()
        # __enter__ is consumed in call order: the args file write, then
        # _generate_backend_override_file()'s own `with open(...)`, then the Makefile write
        mock_open.return_value.__enter__.side_effect = [mock_args_file, mock_backend_override_file, mock_makefile]

        mock_makefile_rules = Mock()
        mock_pending_args_files = [
            PendingArgsFile(path="/output/dir/aaaa.args.json", expression="expr", target="target"),
        ]
        mock_output_directory_path = "/output/dir"

        with patch("samcli.hook_packages.terraform.hooks.prepare.makefile_generator.json") as mock_json:
            generate_makefile(mock_makefile_rules, mock_pending_args_files, mock_output_directory_path)

            mock_json.dump.assert_called_once_with({"expression": "expr", "target": "target"}, mock_args_file)

        if output_dir_exists:
            mock_os.makedirs.assert_not_called()
        else:
            mock_os.makedirs.assert_called_once_with(mock_output_directory_path, exist_ok=True)

        # stale *.args.json files from a previous run are removed before this run's set is written
        mock_glob.glob.assert_called_once_with("/output/dir/*.args.json")

        mock_shutil.copy.assert_has_calls(
            [
                call(mock_copy_terraform_built_artifacts_script_path, mock_output_directory_path),
                call(mock_zip_module_path, mock_output_directory_path),
            ]
        )
        mock_makefile.writelines.assert_called_once_with(mock_makefile_rules)

    def test_generate_makefile_prunes_stale_args_files_and_writes_new_ones(self):
        # End-to-end (real filesystem) check of the two behaviors this test's mocked sibling
        # can't observe directly: a *.args.json left behind by a previous run (e.g. for a Lambda
        # resource that has since been renamed or removed) is deleted, and every current
        # PendingArgsFile is written with its expression/target intact - including values that
        # were previously dangerous when embedded directly in a shell command line (backticks,
        # $(...), embedded newlines, quotes, etc), which JSON encoding neutralizes without
        # needing any shell- or make-specific escaping.
        with tempfile.TemporaryDirectory() as output_dir:
            stale_args_file_path = os.path.join(output_dir, "stale0000.args.json")
            with open(stale_args_file_path, "w") as f:
                f.write('{"expression": "old", "target": "old"}')

            malicious_value = 'null_resource.sam_metadata["normal`touch /tmp/poc_sam_rce`"]'
            pending_args_files = [
                PendingArgsFile(
                    path=os.path.join(output_dir, "current1.args.json"),
                    expression=malicious_value,
                    target=malicious_value,
                ),
            ]

            generate_makefile(["build-x:\n\techo hi\n"], pending_args_files, output_dir)

            self.assertFalse(os.path.exists(stale_args_file_path))
            with open(pending_args_files[0].path) as f:
                contents = json.load(f)
            self.assertEqual(contents, {"expression": malicious_value, "target": malicious_value})
