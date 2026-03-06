"""
Integration tests for sam validate with Language Extensions error cases.
"""

from pathlib import Path
from unittest import TestCase, skipIf

from tests.testing_utils import (
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    run_command,
    get_sam_command,
)

# Validate tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_TESTS, "Skip validate tests in CI/CD only")
class TestValidateLanguageExtensions(TestCase):
    """Integration tests for validate command with Language Extensions."""

    @classmethod
    def setUpClass(cls):
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "validate")

    def test_depth_limit_validation_fails(self):
        """TC-008: Nested ForEach exceeding depth limit should fail."""
        template_path = self.test_data_path.joinpath("language-extensions-depth-limit", "template.yaml")

        cmdlist = [get_sam_command(), "validate", "--template-file", str(template_path)]
        result = run_command(cmdlist)

        # Should fail validation
        self.assertNotEqual(result.process.returncode, 0)
        stderr = result.stderr.decode("utf-8")

        # Should mention depth or nesting
        self.assertTrue(
            "depth" in stderr.lower() or "nest" in stderr.lower(), f"Error should mention depth/nesting: {stderr}"
        )

    def test_invalid_syntax_validation_fails(self):
        """TC-009: Invalid ForEach syntax should fail."""
        template_path = self.test_data_path.joinpath("language-extensions-invalid-syntax", "template.yaml")

        cmdlist = [get_sam_command(), "validate", "--template-file", str(template_path)]
        result = run_command(cmdlist)

        # Should fail validation
        self.assertNotEqual(result.process.returncode, 0)
        stderr = result.stderr.decode("utf-8")

        # Should mention ForEach or syntax
        self.assertTrue(
            "foreach" in stderr.lower() or "syntax" in stderr.lower(), f"Error should mention ForEach/syntax: {stderr}"
        )

    def test_missing_parameter_validation_fails(self):
        """TC-010: Missing parameter reference should fail."""
        template_path = self.test_data_path.joinpath("language-extensions-missing-param", "template.yaml")

        cmdlist = [get_sam_command(), "validate", "--template-file", str(template_path)]
        result = run_command(cmdlist)

        # Should fail validation
        self.assertNotEqual(result.process.returncode, 0)
