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

    def test_build_zipfile_fnsub_preserves_intrinsic(self):
        """Regression for #9029: `Code.ZipFile: !Sub ...` on a Lambda function under
        AWS::LanguageExtensions must round-trip through `sam build` with the Fn::Sub
        intact. Before the fix, the LE-aware merge step copied the LE-resolved value
        back, baking default pseudo-parameter values (us-east-1, 123456789012) into
        the built template."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-zipfile-fnsub", "template.yaml"))

        cmdlist = self.get_command_list()
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, f"Build failed: {command_result.stderr.decode('utf-8')}")

        built_template_path = self.default_build_dir.joinpath("template.yaml")
        self.assertTrue(built_template_path.exists())

        with open(built_template_path, "r") as f:
            built_template = yaml.safe_load(f)

        function_props = built_template["Resources"]["MyTriggerFunction"]["Properties"]

        # Code.ZipFile must remain a dict containing Fn::Sub, not a resolved string.
        zipfile_value = function_props["Code"]["ZipFile"]
        self.assertIsInstance(
            zipfile_value, dict, f"Expected Code.ZipFile to remain a Fn::Sub dict, got: {zipfile_value!r}"
        )
        self.assertIn("Fn::Sub", zipfile_value)
        sub_body = zipfile_value["Fn::Sub"]
        self.assertIn("${AWS::Region}", sub_body)
        self.assertIn("${AWS::AccountId}", sub_body)
        # Confirm no default pseudo-param values leaked through.
        self.assertNotIn("us-east-1", sub_body)
        self.assertNotIn("123456789012", sub_body)

        # Role's Fn::Sub should likewise be preserved (sanity check on the same merge path).
        role_value = function_props["Role"]
        self.assertIsInstance(role_value, dict)
        self.assertIn("Fn::Sub", role_value)
        self.assertIn("${AWS::AccountId}", role_value["Fn::Sub"])

    def test_build_foreach_static_zipfile_fnsub_preserves_intrinsic(self):
        """Regression for #9029 (ForEach static branch / case B): inside a
        Fn::ForEach body, `Code.ZipFile: !Sub ...` whose body does NOT reference
        the loop variable must round-trip through `sam build` with the Fn::Sub
        intact. The static-branch merge has no build artifact for an inline-source
        Lambda, so the user-authored property must be preserved verbatim."""
        self.template_path = str(
            Path(self.test_data_path, "language-extensions-foreach-zipfile-static", "template.yaml")
        )

        cmdlist = self.get_command_list()
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, f"Build failed: {command_result.stderr.decode('utf-8')}")

        built_template_path = self.default_build_dir.joinpath("template.yaml")
        self.assertTrue(built_template_path.exists())

        with open(built_template_path, "r") as f:
            built_template = yaml.safe_load(f)

        # Fn::ForEach structure must be preserved
        resources = built_template.get("Resources", {})
        foreach_block = resources.get("Fn::ForEach::Workers")
        self.assertIsNotNone(foreach_block, "Fn::ForEach::Workers must survive in built template")
        self.assertEqual(foreach_block[0], "WorkerName")
        self.assertEqual(foreach_block[1], ["Alpha", "Beta"])

        # The body's Code.ZipFile must remain a Fn::Sub dict, not a resolved string,
        # and must still reference ${AWS::Region} / ${AWS::AccountId}.
        body = foreach_block[2]
        worker_props = body["${WorkerName}Worker"]["Properties"]
        zipfile_value = worker_props["Code"]["ZipFile"]
        self.assertIsInstance(zipfile_value, dict)
        self.assertIn("Fn::Sub", zipfile_value)
        sub_body = zipfile_value["Fn::Sub"]
        self.assertIn("${AWS::Region}", sub_body)
        self.assertIn("${AWS::AccountId}", sub_body)
        self.assertNotIn("us-east-1", sub_body)
        self.assertNotIn("123456789012", sub_body)

    def test_build_foreach_dynamic_inline_zipfile_preserved(self):
        """Regression for #9029 (ForEach dynamic branch / case C): inside a
        Fn::ForEach body, a property that references the loop variable but produces
        no build artifact for any iteration (e.g. inline-source `Code.ZipFile`) is
        passed through verbatim. CFN's LanguageExtensions transform expands the
        ForEach at deploy time, substituting the loop variable in each per-iteration
        copy, so the inline body works correctly without a SAM-built artifact."""
        self.template_path = str(
            Path(self.test_data_path, "language-extensions-foreach-zipfile-dynamic", "template.yaml")
        )

        cmdlist = self.get_command_list()
        command_result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(command_result.process.returncode, 0, f"Build failed: {command_result.stderr.decode('utf-8')}")

        built_template_path = self.default_build_dir.joinpath("template.yaml")
        with open(built_template_path, "r") as f:
            built_template = yaml.safe_load(f)

        resources = built_template.get("Resources", {})
        foreach_block = resources["Fn::ForEach::Workers"]
        body = foreach_block[2]
        worker_props = body["${WorkerName}Worker"]["Properties"]
        zipfile_value = worker_props["Code"]["ZipFile"]
        # The inline ZipFile must remain a Fn::Sub dict with both the loop
        # variable and pseudo-parameter intrinsics intact — neither resolved
        # at build time nor replaced by a Mapping lookup.
        self.assertIsInstance(zipfile_value, dict)
        self.assertIn("Fn::Sub", zipfile_value)
        sub_body = zipfile_value["Fn::Sub"]
        self.assertIn("${WorkerName}", sub_body)
        role_value = worker_props["Role"]
        self.assertIsInstance(role_value, dict)
        self.assertIn("Fn::Sub", role_value)
        self.assertIn("${AWS::AccountId}", role_value["Fn::Sub"])

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
