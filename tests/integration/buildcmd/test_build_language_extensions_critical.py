"""
Critical integration tests for CloudFormation Language Extensions.
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
class TestBuildLanguageExtensionsCritical(BuildIntegBase):
    """Critical integration tests for Language Extensions."""

    template = "language-extensions-simple-foreach/template.yaml"

    def _get_python_version(self):
        return f"python{sys.version_info.major}.{sys.version_info.minor}"

    def test_simple_foreach_static_codeuri(self):
        """TC-001: Simple ForEach with static CodeUri."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-simple-foreach", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for func in ["AlphaFunction", "BetaFunction", "GammaFunction"]:
            self.assertTrue(self.default_build_dir.joinpath(func).exists())

    def test_foreach_with_dynamodb_streams(self):
        """TC-019: ForEach with DynamoDB tables and stream processors."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-dynamodb", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for table in ["Users", "Orders", "Products"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{table}StreamProcessor").exists())

    def test_foreach_with_sns_topics(self):
        """TC-017: ForEach with SNS topics and handlers."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-sns-topics", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for topic in ["OrderEvents", "PaymentEvents", "ShippingEvents"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{topic}Handler").exists())

    def test_foreach_with_s3_buckets(self):
        """TC-018: ForEach with S3 buckets and processors."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-s3-buckets", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for bucket in ["uploads", "thumbnails", "exports"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{bucket}Processor").exists())

    def test_foreach_with_api_definition(self):
        """TC-020: ForEach with dynamic API DefinitionUri."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-api-definition", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        for version in ["v1", "v2", "v3"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{version}Handler").exists())

    def test_foreach_with_layers(self):
        """TC-023: ForEach with Lambda layers."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-layers", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        # Layers are packaged, not built - verify TestFunction built
        self.assertTrue(self.default_build_dir.joinpath("TestFunction").exists())

    def test_foreach_mixed_artifacts(self):
        """TC-024: ForEach with multiple artifact types."""
        self.template_path = str(Path(self.test_data_path, "language-extensions-mixed-artifacts", "template.yaml"))
        overrides = {"Runtime": self._get_python_version()}
        cmdlist = self.get_command_list(parameter_overrides=overrides)
        result = run_command(cmdlist, cwd=self.working_dir)

        self.assertEqual(result.process.returncode, 0)
        # Verify functions built (layers are packaged, not built)
        for service in ["users", "orders"]:
            self.assertTrue(self.default_build_dir.joinpath(f"{service}Function").exists())
