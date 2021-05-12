"""
Integration tests for sam validate
"""

import os
import re
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional
from unittest import TestCase

from parameterized import parameterized
from tests.testing_utils import run_command


class TemplateFileTypes(Enum):
    JSON = auto()
    YAML = auto()


class TestValidate(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = {
            TemplateFileTypes.JSON: re.compile(r"^/.+/template[.]json is a valid SAM Template$"),
            TemplateFileTypes.YAML: re.compile(r"^/.+/template[.]yaml is a valid SAM Template$"),
        }

    @staticmethod
    def base_command() -> str:
        return "samdev" if os.getenv("SAM_CLI_DEV") else "sam"

    def command_list(
        self,
        template_file: Optional[Path] = None,
        profile: Optional[str] = None,
        region: Optional[str] = None,
        config_file: Optional[Path] = None,
    ) -> List[str]:
        command_list = [self.base_command(), "validate"]
        if template_file:
            command_list += ["--template-file", str(template_file)]
        if profile:
            command_list += ["--profile", profile]
        if region:
            command_list += ["--region", region]
        if config_file:
            command_list = ["--config_file", str(config_file)]
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
    def test_default_template(self, relative_folder: str, expected_file: TemplateFileTypes):
        cwd = f"tests/integration/testdata/validate/{relative_folder}"
        command_result = run_command(self.command_list(), cwd=cwd)
        pattern = self.patterns[expected_file]
        output = command_result.stdout.decode("utf-8")
        self.assertEqual(command_result.process.returncode, 0)
        self.assertIsNotNone(pattern.match(output))
