"""
Integration tests for sam validate
"""

import json
import os
import re
import tempfile
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional
from unittest import TestCase, skip
from unittest.case import skipIf

import pytest
from parameterized import parameterized
from tests.testing_utils import (
    RUN_BY_CANARY,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    run_command,
    get_sam_command,
)

from cfnlint.helpers import load_resource
from cfnlint.data import AdditionalSpecs


# cfn-lint has a dynamic validation for deprecated runtimes depending on the date, and the error will change according to that
# some of the logic from cfn-lint):
# https://github.com/aws-cloudformation/cfn-lint/blob/baa4f017592fc56f7f11f10d22c8044ff36c3f6a/src/cfnlint/rules/resources/lmbd/DeprecatedRuntimeEol.py#L32
def get_runtime_deprecation_values(runtime):
    current_date = datetime.today()
    # Runtime deprecation dates: https://github.com/aws-cloudformation/cfn-lint/blob/main/src/cfnlint/data/AdditionalSpecs/LmbdRuntimeLifecycle.json
    deprecated_runtimes = load_resource(AdditionalSpecs, "LmbdRuntimeLifecycle.json")
    runtime_data = deprecated_runtimes.get(runtime)
    # Not deprecated
    if not runtime_data or current_date < datetime.strptime(runtime_data["deprecated"], "%Y-%m-%d"):
        return None
    # Deprecated but not create-blocked yet
    if current_date < datetime.strptime(runtime_data["create-block"], "%Y-%m-%d"):
        return {"code": "W2531", "msg": "Check if EOL Lambda Function Runtimes are used"}
    # Create-blocked but not update-blocked
    if current_date < datetime.strptime(runtime_data["update-block"], "%Y-%m-%d"):
        return {"code": "E2531", "msg": "Validate if lambda runtime is deprecated"}
    # Fully deprecated including update-blocked
    return {"code": "E2533", "msg": "Check if Lambda Function Runtimes are updatable"}


# Validate tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_VALIDATE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


class TemplateFileTypes(Enum):
    JSON = auto()
    YAML = auto()


@skipIf(SKIP_VALIDATE_TESTS, "Skip validate tests in CI/CD only")
class TestValidate(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = {
            TemplateFileTypes.JSON: re.compile(
                r"template\.json is a valid SAM Template. This is according to basic SAM Validation, "
                'for additional validation, please run with "--lint" option(\r\n)?$'
            ),
            TemplateFileTypes.YAML: re.compile(
                r"template\.yaml is a valid SAM Template. This is according to basic SAM Validation, "
                'for additional validation, please run with "--lint" option(\r\n)?$'
            ),
        }
        cls.lint_patterns = {
            TemplateFileTypes.JSON: re.compile(r"template\.json is a valid SAM Template(\r\n)?$"),
            TemplateFileTypes.YAML: re.compile(r"template\.yaml is a valid SAM Template(\r\n)?$"),
        }

    def command_list(
        self,
        template_file: Optional[Path] = None,
        profile: Optional[str] = None,
        region: Optional[str] = None,
        config_file: Optional[Path] = None,
        lint: Optional[bool] = None,
    ) -> List[str]:
        command_list = [get_sam_command(), "validate"]
        if template_file:
            command_list += ["--template-file", str(template_file)]
        if profile:
            command_list += ["--profile", profile]
        if region:
            command_list += ["--region", region]
        if config_file:
            command_list += ["--config_file", str(config_file)]
        if lint:
            command_list += ["--lint"]
        return command_list

    @parameterized.expand(
        [
            ("default_yaml", TemplateFileTypes.YAML),  # project with template.yaml
            ("default_json", TemplateFileTypes.JSON),  # project with template.json
            ("multiple_files", TemplateFileTypes.YAML),  # project with both template.yaml and template.json
            (
                "with_build",
                TemplateFileTypes.JSON,
            ),  # project with template.json and standard build directory .aws-sam/build/template.yaml
        ]
    )
    @pytest.mark.tier1
    def test_default_template_file_choice(self, relative_folder: str, expected_file: TemplateFileTypes):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate"
        process_dir = test_data_path / relative_folder
        command_result = run_command(self.command_list(), cwd=str(process_dir))
        pattern = self.patterns[expected_file]  # type: ignore
        output = command_result.stdout.decode("utf-8")
        self.assertEqual(command_result.process.returncode, 0)
        self.assertRegex(output, pattern)

    def test_validate_logs_warning_for_cdk_project(self):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "package"
        template_file = "aws-serverless-function-cdk.yaml"
        template_path = test_data_path.joinpath(template_file)
        command_result = run_command(self.command_list(template_file=template_path))
        output = command_result.stdout.decode("utf-8")

        warning_message = (
            f"Warning: CDK apps are not officially supported with this command.{os.linesep}"
            "We recommend you use this alternative command: cdk doctor"
        )

        self.assertIn(warning_message, output)

    @parameterized.expand(
        [
            ("default_yaml", TemplateFileTypes.YAML),  # project with template.yaml
            ("default_json", TemplateFileTypes.JSON),  # project with template.json
            ("multiple_files", TemplateFileTypes.YAML),  # project with both template.yaml and template.json
            (
                "with_build",
                TemplateFileTypes.JSON,
            ),  # project with template.json and standard build directory .aws-sam/build/template.yaml
        ]
    )
    def test_lint_template(self, relative_folder: str, expected_file: TemplateFileTypes):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate"
        process_dir = test_data_path / relative_folder
        command_result = run_command(self.command_list(lint=True), cwd=str(process_dir))
        pattern = self.lint_patterns[expected_file]  # type: ignore
        output = command_result.stdout.decode("utf-8")
        self.assertEqual(command_result.process.returncode, 0)
        self.assertRegex(output, pattern)

    @parameterized.expand(
        [
            ("nodejs",),
            ("python3.7",),
            ("nodejs16.x",),
            ("nodejs18.x",),
        ]
    )
    def test_lint_deprecated_runtimes(self, runtime):

        # The message for deprecated runtimes can change according to the current date
        deprecation_values = get_runtime_deprecation_values(runtime)
        if not deprecation_values:
            self.fail(f"Runtime {runtime} is not marked as deprecated. This shouldn't happen in this test.")
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "HelloWorldFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "HelloWorldFunction",
                        "Handler": "app.lambdaHandler",
                        "Runtime": runtime,
                    },
                }
            },
        }

        with tempfile.TemporaryDirectory() as temp:
            template_file = Path(temp, "template.json")
            with open(template_file, "w") as f:
                f.write(json.dumps(template, indent=4) + "\n")

            command_result = run_command(self.command_list(lint=True), cwd=str(temp))

            output = command_result.stdout.decode("utf-8")
            self.assertEqual(command_result.process.returncode, 1)
            self.assertIn(
                f"[[{deprecation_values['code']}: {deprecation_values['msg']}] (Runtime '{runtime}' was deprecated on ",
                output,
            )

    def test_lint_supported_runtimes(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {},
        }
        supported_runtimes = [
            "dotnet10",
            "dotnet8",
            "java21",
            "java17",
            "java11",
            "java8.al2",
            "nodejs20.x",
            "nodejs22.x",
            "provided.al2",
            "provided.al2023",
            "python3.10",
            "python3.11",
            "python3.12",
            "python3.13",
            "ruby3.2",
            "ruby3.3",
            "ruby3.4",
        ]
        i = 0
        for runtime in supported_runtimes:
            i += 1
            template["Resources"][f"HelloWorldFunction{i}"] = {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "HelloWorldFunction",
                    "Handler": "app.lambdaHandler",
                    "Runtime": runtime,
                },
            }
        with tempfile.TemporaryDirectory() as temp:
            template_file = Path(temp, "template.json")
            with open(template_file, "w") as f:
                f.write(json.dumps(template, indent=4) + "\n")
            command_result = run_command(self.command_list(lint=True), cwd=str(temp))
            pattern = self.lint_patterns[TemplateFileTypes.JSON]
            output = command_result.stdout.decode("utf-8")
            self.assertEqual(command_result.process.returncode, 0)
            self.assertRegex(output, pattern)

    def test_lint_error_no_region(self):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "default_json"
        template_file = "template.json"
        template_path = test_data_path.joinpath(template_file)
        command_result = run_command(self.command_list(lint=True, region="--debug", template_file=template_path))
        output = command_result.stderr.decode("utf-8")

        error_message = f"Error: Provided region: --debug doesn't match a supported format"

        self.assertIn(error_message, output)

    def test_lint_error_invalid_region(self):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "default_json"
        template_file = "template.json"
        template_path = test_data_path.joinpath(template_file)
        command_result = run_command(self.command_list(lint=True, region="us-north-5", template_file=template_path))
        output = command_result.stderr.decode("utf-8")

        error_message = (
            f"Error: AWS Region was not found. Please configure your region through the --region option.{os.linesep}"
            f"Regions ['us-north-5'] are unsupported. Supported regions are"
        )

        self.assertIn(error_message, output)

    def test_lint_invalid_template(self):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "default_yaml"
        template_file = "templateError.yaml"
        template_path = test_data_path.joinpath(template_file)
        command_result = run_command(self.command_list(lint=True, template_file=template_path))
        output = command_result.stdout.decode("utf-8")
        # Remove Windows Line Endings for comparison.
        output = output.replace("\r", "")

        warning_message = (
            "[[E0000: Parsing error found when parsing the template] "
            "(Duplicate found 'HelloWorldFunction' (line 5)) matched 5, "
            "[E0000: Parsing error found when parsing the template] "
            "(Duplicate found 'HelloWorldFunction' (line 12)) matched 12]\n"
        )

        self.assertIn(warning_message, output)
        self.assertEqual(command_result.process.returncode, 1)

    def test_validate_language_extensions_valid_foreach(self):
        """
        Test that sam validate passes for valid Fn::ForEach syntax.

        Validates: Requirements 7.1, 12.3
        - 7.1: WHEN `sam validate` processes a template with valid `Fn::ForEach` syntax,
               THE Validate_Command SHALL report the template as valid
        - 12.3: THE Integration_Tests SHALL verify `sam validate` correctly validates
                templates with language extensions
        """
        test_data_path = (
            Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "language-extensions"
        )
        template_file = "valid-foreach.yaml"
        template_path = test_data_path / template_file

        command_result = run_command(self.command_list(template_file=template_path))
        output = command_result.stdout.decode("utf-8")

        # Verify the command succeeds (exit code 0)
        self.assertEqual(
            command_result.process.returncode,
            0,
            f"Expected exit code 0 but got {command_result.process.returncode}. Output: {output}",
        )

        # Verify the output indicates the template is valid
        # The output should contain a message indicating the template is valid
        valid_pattern = re.compile(
            r"valid-foreach\.yaml is a valid SAM Template\. This is according to basic SAM Validation, "
            'for additional validation, please run with "--lint" option(\r\n)?$'
        )
        self.assertRegex(
            output,
            valid_pattern,
            f"Expected output to indicate template is valid. Actual output: {output}",
        )

    def test_validate_language_extensions_invalid_foreach(self):
        """
        Test that sam validate fails with clear error message for invalid Fn::ForEach syntax.

        Validates: Requirements 7.2, 12.4
        - 7.2: WHEN `sam validate` processes a template with invalid `Fn::ForEach` syntax
               (e.g., wrong number of arguments), THE Validate_Command SHALL report a
               clear error message
        - 12.4: THE Integration_Tests SHALL verify `sam validate` reports errors for
                invalid language extension syntax
        """
        test_data_path = (
            Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "language-extensions"
        )
        template_file = "invalid-foreach.yaml"
        template_path = test_data_path / template_file

        command_result = run_command(self.command_list(template_file=template_path))
        # Combine stdout and stderr for error message checking
        stdout_output = command_result.stdout.decode("utf-8")
        stderr_output = command_result.stderr.decode("utf-8")
        combined_output = stdout_output + stderr_output

        # Verify the command fails (non-zero exit code)
        self.assertNotEqual(
            command_result.process.returncode,
            0,
            f"Expected non-zero exit code but got {command_result.process.returncode}. Output: {combined_output}",
        )

        # Verify the output contains the specific error about invalid ForEach layout
        self.assertIn(
            "layout is incorrect",
            combined_output,
            f"Expected 'layout is incorrect' error for invalid Fn::ForEach syntax. Actual output: {combined_output}",
        )

    def test_validate_language_extensions_valid_dynamic_codeuri(self):
        """
        Test that sam validate passes for valid Fn::ForEach with dynamic CodeUri.

        Validates: Requirements 4.1, 10.1
        - 4.1: Dynamic artifact properties (e.g., CodeUri: ./${Name}) are supported
        - 10.1: sam validate should pass for valid templates with dynamic CodeUri
        """
        test_data_path = (
            Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "language-extensions"
        )
        template_file = "valid-dynamic-codeuri.yaml"
        template_path = test_data_path / template_file

        command_result = run_command(self.command_list(template_file=template_path))
        output = command_result.stdout.decode("utf-8")

        # Verify the command succeeds (exit code 0)
        self.assertEqual(
            command_result.process.returncode,
            0,
            f"Expected exit code 0 but got {command_result.process.returncode}. Output: {output}",
        )

        # Verify the output indicates the template is valid
        valid_pattern = re.compile(
            r"valid-dynamic-codeuri\.yaml is a valid SAM Template\. This is according to basic SAM Validation, "
            'for additional validation, please run with "--lint" option(\r\n)?$'
        )
        self.assertRegex(
            output,
            valid_pattern,
            f"Expected output to indicate template is valid. Actual output: {output}",
        )

    def test_validate_language_extensions_cloud_dependent_collection(self):
        """
        Test that sam validate fails with clear error for cloud-dependent collection.

        Validates: Requirements 5.1, 5.4, 5.5
        - 5.1: Fn::GetAtt in collection should raise error with clear message
        - 5.4: Error message should include which Fn::ForEach block has the issue
        - 5.5: Error message should suggest using parameter with --parameter-overrides
        """
        test_data_path = (
            Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "language-extensions"
        )
        template_file = "cloud-dependent-collection.yaml"
        template_path = test_data_path / template_file

        command_result = run_command(self.command_list(template_file=template_path))
        # Combine stdout and stderr for error message checking
        stdout_output = command_result.stdout.decode("utf-8")
        stderr_output = command_result.stderr.decode("utf-8")
        combined_output = stdout_output + stderr_output

        # Verify the command fails (non-zero exit code)
        self.assertNotEqual(
            command_result.process.returncode,
            0,
            f"Expected non-zero exit code but got {command_result.process.returncode}. Output: {combined_output}",
        )

        # Verify the output contains the specific error about unresolvable collection
        self.assertIn(
            "Unable to resolve Fn::ForEach collection locally",
            combined_output,
            f"Expected 'Unable to resolve Fn::ForEach collection locally' error. Actual output: {combined_output}",
        )

    def test_validate_language_extensions_missing_dynamic_artifact_dir(self):
        """
        Test that sam validate handles templates with dynamic CodeUri pointing to non-existent directories.

        Validates: Requirements 4.1
        - 4.1: Dynamic artifact properties should be validated

        Note: sam validate performs basic SAM validation which may not check if directories exist.
        This test verifies the behavior when dynamic CodeUri points to non-existent directories.
        """
        test_data_path = (
            Path(__file__).resolve().parents[2] / "integration" / "testdata" / "validate" / "language-extensions"
        )
        template_file = "missing-dynamic-artifact-dir.yaml"
        template_path = test_data_path / template_file

        command_result = run_command(self.command_list(template_file=template_path))
        stdout_output = command_result.stdout.decode("utf-8")
        stderr_output = command_result.stderr.decode("utf-8")
        combined_output = stdout_output + stderr_output

        # sam validate performs basic SAM template validation only — it does not check
        # whether artifact directories exist on disk. Directory validation happens at
        # build time. The template is syntactically valid, so validate should pass.
        self.assertEqual(
            command_result.process.returncode,
            0,
            f"sam validate should pass for syntactically valid template (directory checks happen at build time). "
            f"Output: {combined_output}",
        )

    def test_validate_language_extensions_nested_foreach_valid_depth_5(self):
        """
        Test that sam validate passes for templates with 5 levels of nested Fn::ForEach.

        Validates: Requirements 18.2, 18.6
        - 18.2: WHEN a template contains 5 or fewer levels of nested Fn::ForEach loops,
                THE SAM_CLI SHALL process the template successfully
        - 18.6: WHEN `sam validate` processes a template exceeding the nested loop limit,
                THE Validate_Command SHALL report the nesting depth error
        """
        test_data_path = (
            Path(__file__).resolve().parents[2]
            / "integration"
            / "testdata"
            / "buildcmd"
            / "language-extensions-nested-foreach-valid"
        )
        template_file = "template.yaml"
        template_path = test_data_path / template_file

        command_result = run_command(self.command_list(template_file=template_path))
        output = command_result.stdout.decode("utf-8")

        # Verify the command succeeds (exit code 0)
        self.assertEqual(
            command_result.process.returncode,
            0,
            f"Expected exit code 0 but got {command_result.process.returncode}. Output: {output}",
        )

        # Verify the output indicates the template is valid
        valid_pattern = re.compile(
            r"template\.yaml is a valid SAM Template\. This is according to basic SAM Validation, "
            'for additional validation, please run with "--lint" option(\r\n)?$'
        )
        self.assertRegex(
            output,
            valid_pattern,
            f"Expected output to indicate template is valid. Actual output: {output}",
        )

    def test_validate_language_extensions_nested_foreach_invalid_depth_6(self):
        """
        Test that sam validate fails for templates with 6 levels of nested Fn::ForEach.

        Validates: Requirements 18.3, 18.4, 18.5, 18.6
        - 18.3: WHEN a template contains more than 5 levels of nested Fn::ForEach loops,
                THE SAM_CLI SHALL raise an error before processing
        - 18.4: WHEN the nested loop limit is exceeded, THE error message SHALL clearly
                indicate that the maximum nesting depth of 5 has been exceeded
        - 18.5: WHEN the nested loop limit is exceeded, THE error message SHALL indicate
                the actual nesting depth found in the template
        - 18.6: WHEN `sam validate` processes a template exceeding the nested loop limit,
                THE Validate_Command SHALL report the nesting depth error
        """
        test_data_path = (
            Path(__file__).resolve().parents[2]
            / "integration"
            / "testdata"
            / "buildcmd"
            / "language-extensions-nested-foreach-invalid"
        )
        template_file = "template.yaml"
        template_path = test_data_path / template_file

        command_result = run_command(self.command_list(template_file=template_path))
        # Combine stdout and stderr for error message checking
        stdout_output = command_result.stdout.decode("utf-8")
        stderr_output = command_result.stderr.decode("utf-8")
        combined_output = stdout_output + stderr_output

        # Verify the command fails (non-zero exit code)
        self.assertNotEqual(
            command_result.process.returncode,
            0,
            f"Expected non-zero exit code but got {command_result.process.returncode}. Output: {combined_output}",
        )

        # Requirement 18.4: Error message indicates maximum nesting depth of 5
        self.assertIn(
            "5",
            combined_output,
            f"Expected error message to mention maximum depth of 5. Actual output: {combined_output}",
        )

        # Requirement 18.5: Error message indicates actual nesting depth found (6)
        self.assertIn(
            "6",
            combined_output,
            f"Expected error message to mention actual depth of 6. Actual output: {combined_output}",
        )

        # Verify the error message mentions nesting or depth
        nesting_indicators = ["nesting", "depth", "exceeds", "maximum", "nested"]
        has_nesting_indicator = any(indicator.lower() in combined_output.lower() for indicator in nesting_indicators)
        self.assertTrue(
            has_nesting_indicator,
            f"Expected error message about nesting depth. Actual output: {combined_output}",
        )
