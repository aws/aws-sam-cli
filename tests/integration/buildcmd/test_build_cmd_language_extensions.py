"""
Integration tests for sam build with CloudFormation Language Extensions.

Tests that sam build correctly processes templates using AWS::LanguageExtensions
transform, including Fn::ForEach expansion, dynamic CodeUri with Mappings generation,
and nested Fn::ForEach.
"""

import logging
import os
import sys
from pathlib import Path

import pytest
import yaml

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import run_command

LOG = logging.getLogger(__name__)


@pytest.mark.python
class TestBuildCommand_LanguageExtensions(BuildIntegBase):
    """Integration tests for sam build with CloudFormation Language Extensions."""

    template = "language-extensions.yaml"

    EXPECTED_FILES_PROJECT_MANIFEST = {
        "__init__.py",
        "main.py",
    }

    FOREACH_GENERATED_FUNCTIONS = ["AlphaFunction", "BetaFunction"]
    CONFIG_FUNCTION = "ConfigFunction"

    def _get_python_version(self):
        return f"python{sys.version_info.major}.{sys.version_info.minor}"

    def _verify_function_built(self, function_logical_id: str):
        build_dir_files = os.listdir(str(self.default_build_dir))
        self.assertIn(function_logical_id, build_dir_files)

        resource_artifact_dir = self.default_build_dir.joinpath(function_logical_id)
        self.assertTrue(resource_artifact_dir.exists())

        all_artifacts = set(os.listdir(str(resource_artifact_dir)))
        actual_files = all_artifacts.intersection(self.EXPECTED_FILES_PROJECT_MANIFEST)
        self.assertEqual(actual_files, self.EXPECTED_FILES_PROJECT_MANIFEST)

    @pytest.mark.tier1_extra
    def test_build_with_foreach_template(self):
        """Test that sam build expands Fn::ForEach and builds each generated function."""
        runtime = self._get_python_version()
        overrides = {"Runtime": runtime}
        cmdlist = self.get_command_list(parameter_overrides=overrides)

        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, f"Build failed: {command_result.stderr.decode('utf-8')}")
        self.assertTrue(self.default_build_dir.exists())
        self.assertIn("template.yaml", os.listdir(str(self.default_build_dir)))

        for function_name in self.FOREACH_GENERATED_FUNCTIONS:
            self._verify_function_built(function_name)
        self._verify_function_built(self.CONFIG_FUNCTION)

    def test_build_dynamic_codeuri_generates_mappings(self):
        """Test that dynamic CodeUri generates Mappings and Fn::FindInMap in the built template."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-dynamic-codeuri", "template.yaml"))

        runtime = self._get_python_version()
        overrides = {"Runtime": runtime}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, f"Build failed: {command_result.stderr.decode('utf-8')}")

        built_template_path = self.default_build_dir.joinpath("template.yaml")
        self.assertTrue(built_template_path.exists())

        with open(built_template_path, "r") as f:
            built_template = yaml.safe_load(f)

        # Verify Fn::ForEach preserved
        resources = built_template.get("Resources", {})
        foreach_key = "Fn::ForEach::Functions"
        self.assertIn(foreach_key, resources)

        foreach_block = resources[foreach_key]
        self.assertEqual(foreach_block[0], "FunctionName")
        self.assertEqual(foreach_block[1], ["Alpha", "Beta"])

        # Verify Mappings generated
        mappings = built_template.get("Mappings", {})
        mapping_name = "SAMCodeUriFunctions"
        self.assertIn(mapping_name, mappings)
        self.assertIn("Alpha", mappings[mapping_name])
        self.assertIn("Beta", mappings[mapping_name])

        alpha_codeuri = mappings[mapping_name]["Alpha"].get("CodeUri")
        beta_codeuri = mappings[mapping_name]["Beta"].get("CodeUri")
        self.assertIsNotNone(alpha_codeuri)
        self.assertIsNotNone(beta_codeuri)
        self.assertNotEqual(alpha_codeuri, beta_codeuri)

        # Verify CodeUri replaced with Fn::FindInMap
        body = foreach_block[2]
        codeuri = body["${FunctionName}Function"]["Properties"]["CodeUri"]
        self.assertIn("Fn::FindInMap", codeuri)
        self.assertEqual(codeuri["Fn::FindInMap"][0], mapping_name)
        self.assertEqual(codeuri["Fn::FindInMap"][1], {"Ref": "FunctionName"})

    def test_build_nested_foreach_dynamic_codeuri_generates_mappings(self):
        """Test that nested Fn::ForEach with dynamic CodeUri generates Mappings."""
        self.template_path = str(
            Path(self.test_data_path, "language-extensions-nested-foreach-dynamic-codeuri", "template.yaml")
        )

        runtime = self._get_python_version()
        overrides = {"Runtime": runtime}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, f"Build failed: {command_result.stderr.decode('utf-8')}")

        built_template_path = self.default_build_dir.joinpath("template.yaml")
        with open(built_template_path, "r") as f:
            built_template = yaml.safe_load(f)

        # Verify nested ForEach preserved
        resources = built_template.get("Resources", {})
        outer_block = resources["Fn::ForEach::Environments"]
        self.assertEqual(outer_block[0], "Env")
        self.assertEqual(outer_block[1], ["dev", "prod"])

        inner_block = outer_block[2]["Fn::ForEach::Services"]
        self.assertEqual(inner_block[0], "Service")
        self.assertEqual(inner_block[1], ["Users", "Orders"])

        # Verify Mappings generated
        mappings = built_template.get("Mappings", {})
        self.assertIn("SAMCodeUriEnvironmentsServices", mappings)

        # Verify all expanded functions were built
        for env in ["dev", "prod"]:
            for svc in ["Users", "Orders"]:
                func_dir = self.default_build_dir.joinpath(f"{env}{svc}Function")
                self.assertTrue(func_dir.exists(), f"Build artifact for {env}{svc}Function should exist")
