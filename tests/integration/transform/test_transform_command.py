"""
Integration tests for sam transform
"""
import subprocess
# Test Imports

from enum import Enum, auto
import os
import re
from pathlib import Path
from unittest import TestCase
from tests.testing_utils import run_command, run_command_with_input
from typing import List, Optional
from parameterized import parameterized

class TemplateFileTypes(Enum):
    JSON = auto()
    YAML = auto()

class TestTransformCli(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = {
            TemplateFileTypes.JSON: re.compile(r"template\.json is a valid SAM Template(\r\n)?$"),
            TemplateFileTypes.YAML: re.compile(r"template\.yaml is a valid SAM Template(\r\n)?$"),
        }

    
    @staticmethod
    def base_command() -> str:
        return "samdev" 

    def command_list(
        self,
        template_file: Optional[Path] = None,
    ) -> List[str]:
        command_list = [self.base_command(), "transform"]
        if template_file:
            command_list += ["--template", str(template_file)]
        return command_list
    
    @parameterized.expand(
        [
            ("default_yaml", TemplateFileTypes.YAML),  # project with template.yaml
            ("default_json", TemplateFileTypes.JSON),  # project with template.json
        ]
    )
    ## test for checking a valid template transformation
    def test_transformed_template_outputs(self, relative_folder: str, expected_file: TemplateFileTypes):
        test_data_path = Path(__file__).resolve().parents[2] / "integration" / "testdata" / "transform"
        process_dir = test_data_path / relative_folder
        command_result = run_command(self.command_list(), cwd=str(process_dir))
        output = command_result.stdout.decode("utf-8")
        test_output = open("tests/integration/testdata/transform/transformed_template/transformed_yaml", "r")
        checking_output = test_output.read()
        test_output.close()
        self.assertEqual(output, checking_output)
        self.assertEqual(command_result.process.returncode, 0)

    ## test for checking a invalid template transformation
    def test_transformed_template_error(self):
        command_result = run_command([self.base_command(), 'transform', '--template', './testdata/transform/failing_yaml/fail.yaml'])
        self.assertEqual(command_result.process.returncode, 1)