"""
Integration tests for sam generate openapi command
"""

import os
import json
from pathlib import Path
from tests.integration.generate.openapi.generate_openapi_integ_base import GenerateOpenApiIntegBase
from tests.testing_utils import run_command
from samcli.yamlhelper import yaml_parse


class TestGenerateOpenApiCommand(GenerateOpenApiIntegBase):
    """Integration tests for generate openapi command"""

    template = "simple_api.yaml"

    def test_generate_openapi_to_stdout(self):
        """Test generating OpenAPI to stdout"""
        template_path = str(Path(self.test_data_path, self.template))
        command_list = self.get_command_list(template_path=template_path)

        command_result = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)
        stdout = command_result.stdout.decode("utf-8")

        # Verify OpenAPI structure
        openapi_doc = yaml_parse(stdout)
        self.assertIn("swagger", openapi_doc)
        self.assertIn("paths", openapi_doc)
        self.assertIn("/hello", openapi_doc["paths"])

    def test_generate_openapi_to_file(self):
        """Test generating OpenAPI to file"""
        template_path = str(Path(self.test_data_path, self.template))
        output_file = str(self.output_file_path)
        command_list = self.get_command_list(template_path=template_path, output_file=output_file)

        command_result = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)
        self.assertTrue(self.output_file_path.exists())

        # Verify file contents
        with open(output_file, "r") as f:
            openapi_doc = yaml_parse(f.read())
            self.assertIn("swagger", openapi_doc)
            self.assertIn("paths", openapi_doc)

    def test_generate_openapi_json_format(self):
        """Test generating OpenAPI in JSON format"""
        template_path = str(Path(self.test_data_path, self.template))
        command_list = self.get_command_list(template_path=template_path, format="json")

        command_result = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)
        stdout = command_result.stdout.decode("utf-8")

        # Verify JSON format
        openapi_doc = json.loads(stdout)
        self.assertIn("paths", openapi_doc)

    def test_generate_openapi_explicit_api(self):
        """Test generating OpenAPI from explicit API resource"""
        template = "explicit_api.yaml"
        template_path = str(Path(self.test_data_path, template))
        command_list = self.get_command_list(template_path=template_path, api_logical_id="MyApi")

        command_result = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)
        stdout = command_result.stdout.decode("utf-8")
        openapi_doc = yaml_parse(stdout)
        self.assertIn("swagger", openapi_doc)

    def test_generate_openapi_no_api_error(self):
        """Test error when no API resources found"""
        template = "no_api.yaml"
        template_path = str(Path(self.test_data_path, template))
        command_list = self.get_command_list(template_path=template_path)

        command_result = run_command(command_list, cwd=self.working_dir)

        self.assertNotEqual(command_result.process.returncode, 0)
        stderr = command_result.stderr.decode("utf-8")
        self.assertIn("No API resources found", stderr)

    def test_generate_command_group(self):
        """Test that generate command group exists"""
        command_list = [self.cmd, "generate", "--help"]

        command_result = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0)
        stdout = command_result.stdout.decode("utf-8")
        self.assertIn("openapi", stdout)
