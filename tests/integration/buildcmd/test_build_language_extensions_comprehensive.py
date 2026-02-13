"""
Comprehensive integration tests for CloudFormation Language Extensions.
"""

import sys
from pathlib import Path
from unittest import skipIf

import pytest

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUN_BY_CANARY, run_command

SKIP_TESTS = RUNNING_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_TESTS, "Skip tests in CI/CD only")
@pytest.mark.python
class TestBuildLanguageExtensionsComprehensive(BuildIntegBase):
    """Comprehensive integration tests for all Language Extensions scenarios."""

    template = "language-extensions-nested-foreach/template.yaml"

    def _get_python_version(self):
        return f"python{sys.version_info.major}.{sys.version_info.minor}"

    def test_nested_foreach(self):
        """TC-003: Nested ForEach (2 levels)."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-nested-foreach", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for env in ["dev", "prod"]:
            for service in ["api", "worker"]:
                self.assertTrue(self.default_build_dir.joinpath(f"{env}{service}Function").exists())

    def test_empty_collection(self):
        """TC-007: Empty collection should build successfully."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-empty-collection", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)

    def test_foreach_with_conditions(self):
        """TC-011: ForEach with CloudFormation Conditions."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-conditions", "template.yaml"))
        overrides = {"Runtime": self._get_python_version(), "Environment": "prod"}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)

    def test_foreach_with_dependson(self):
        """TC-012: ForEach with DependsOn."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-dependson", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for name in ["reader", "writer"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{name}Function").exists())

    def test_foreach_with_outputs(self):
        """TC-013: ForEach in Outputs section."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-outputs", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)

    def test_large_collection(self):
        """TC-014: Large ForEach collection (50+ items)."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-large-collection", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)

    def test_foreach_with_nested_stacks(self):
        """TC-015: ForEach with nested stacks."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-nested-stacks", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)

    def test_foreach_with_httpapi_definition(self):
        """TC-021: ForEach with HttpApi DefinitionUri."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-httpapi-definition", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for service in ["users", "orders", "inventory"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{service}Function").exists())

    def test_foreach_with_statemachine(self):
        """TC-022: ForEach with Step Functions DefinitionUri."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-statemachine", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for workflow in ["OrderProcessing", "PaymentProcessing", "ShipmentTracking"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{workflow}Worker").exists())

    def test_foreach_with_graphql(self):
        """TC-025: ForEach with GraphQL SchemaUri."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-graphql", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for api in ["public", "internal"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{api}Resolver").exists())

    def test_no_language_extensions_transform(self):
        """TC-016: Template without Language Extensions should work."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-no-transform", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
