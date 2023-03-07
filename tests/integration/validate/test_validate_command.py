"""
Integration tests for sam validate
"""

import os
import re
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional
from unittest import TestCase
from unittest.case import skipIf

from parameterized import parameterized
from tests.testing_utils import (
    RUN_BY_CANARY,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    run_command,
    get_sam_command,
)

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

        error_message = f"Error: AWS Region was not found. Please configure your region through the --region option"

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
            'E0000 Duplicate found "HelloWorldFunction" (line 5)\n'
            f'{os.path.join(test_data_path, "templateError.yaml")}:5:3\n\n'
            'E0000 Duplicate found "HelloWorldFunction" (line 12)\n'
            f'{os.path.join(test_data_path, "templateError.yaml")}:12:3\n\n'
        )

        self.assertIn(warning_message, output)
        self.assertEqual(command_result.process.returncode, 1)
