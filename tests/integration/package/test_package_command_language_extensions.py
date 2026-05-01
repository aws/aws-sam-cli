"""
Integration tests for sam package with CloudFormation Language Extensions.

Tests that sam package correctly handles Fn::ForEach templates, preserving
the original structure and generating Mappings for dynamic artifact properties.
"""

import os
import tempfile
from pathlib import Path
from subprocess import PIPE, Popen, TimeoutExpired
from unittest import skipIf

from samcli.yamlhelper import yaml_parse

from .package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

SKIP_PACKAGE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
TIMEOUT = 300


@skipIf(SKIP_PACKAGE_TESTS, "Skip package tests in CI/CD only")
class TestPackageLanguageExtensions(PackageIntegBase):
    """Integration tests for sam package with CloudFormation Language Extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "package")

    def test_package_preserves_foreach_structure_with_static_codeuri(self):
        """Test that sam package preserves Fn::ForEach structure and uses a shared S3 URI."""
        template_path = self.test_data_path.joinpath("language-extensions-foreach", "template.yaml")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as output_template:
            command_list = PackageIntegBase.get_command_list(
                s3_bucket=self.s3_bucket.name,
                template=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
                force_upload=True,
            )

            process = Popen(command_list, stdout=PIPE, stderr=PIPE)
            try:
                stdout, stderr = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            process_stdout = stdout.strip().decode("utf-8")
            process_stderr = stderr.strip().decode("utf-8")

            self.assertEqual(process.returncode, 0, f"Package failed: stdout={process_stdout}, stderr={process_stderr}")

            with open(output_template.name, "r") as f:
                packaged_template = yaml_parse(f.read())

            # Verify Fn::ForEach preserved
            resources = packaged_template.get("Resources", {})
            foreach_key = "Fn::ForEach::Functions"
            self.assertIn(foreach_key, resources)

            foreach_block = resources[foreach_key]
            self.assertEqual(foreach_block[0], "FunctionName")
            self.assertEqual(foreach_block[1], ["Alpha", "Beta"])

            # Verify CodeUri is S3 URI (shared for static CodeUri)
            function_template = foreach_block[2]["${FunctionName}Function"]
            code_uri = function_template["Properties"]["CodeUri"]
            self.assertIsInstance(code_uri, str)
            self.assertTrue(code_uri.startswith(f"s3://{self.s3_bucket.name}/"))

            os.unlink(output_template.name)

    def test_package_generates_mappings_for_dynamic_codeuri(self):
        """Test that sam package generates Mappings and Fn::FindInMap for dynamic CodeUri."""
        template_path = self.test_data_path.joinpath("language-extensions-dynamic-codeuri", "template.yaml")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as output_template:
            command_list = PackageIntegBase.get_command_list(
                s3_bucket=self.s3_bucket.name,
                template=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
                force_upload=True,
            )

            process = Popen(command_list, stdout=PIPE, stderr=PIPE)
            try:
                stdout, stderr = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            process_stdout = stdout.strip().decode("utf-8")
            process_stderr = stderr.strip().decode("utf-8")

            self.assertEqual(process.returncode, 0, f"Package failed: stdout={process_stdout}, stderr={process_stderr}")

            with open(output_template.name, "r") as f:
                packaged_template = yaml_parse(f.read())

            # Verify Mappings generated
            mappings = packaged_template.get("Mappings", {})
            mapping_name = "SAMCodeUriFunctions"
            self.assertIn(mapping_name, mappings)

            alpha_uri = mappings[mapping_name]["Alpha"]["CodeUri"]
            beta_uri = mappings[mapping_name]["Beta"]["CodeUri"]
            self.assertTrue(alpha_uri.startswith(f"s3://{self.s3_bucket.name}/"))
            self.assertTrue(beta_uri.startswith(f"s3://{self.s3_bucket.name}/"))
            self.assertNotEqual(alpha_uri, beta_uri)

            # Verify Fn::ForEach preserved with Fn::FindInMap
            resources = packaged_template.get("Resources", {})
            foreach_block = resources["Fn::ForEach::Functions"]
            code_uri = foreach_block[2]["${FunctionName}Function"]["Properties"]["CodeUri"]
            self.assertIn("Fn::FindInMap", code_uri)
            self.assertEqual(code_uri["Fn::FindInMap"][0], mapping_name)
            self.assertEqual(code_uri["Fn::FindInMap"][1], {"Ref": "FunctionName"})

            os.unlink(output_template.name)
