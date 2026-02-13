"""
Integration tests for sam sync with Language Extensions.
"""

import sys
from pathlib import Path
from unittest import skipIf

import pytest

from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY, run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_SYNC_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
@pytest.mark.python
class TestSyncLanguageExtensions(SyncIntegBase):
    """Integration tests for sync with Language Extensions."""

    dependency_layer = None

    def _get_python_version(self):
        return f"python{sys.version_info.major}.{sys.version_info.minor}"

    def _testdata_path(self):
        return Path(__file__).resolve().parents[1].joinpath("testdata")

    def _sync_and_verify(self, template_dir):
        """Helper: sync a template from testdata/buildcmd/{template_dir} and verify success."""
        template_path = self._testdata_path().joinpath("buildcmd", template_dir, "template.yaml")
        stack_name = self._method_to_stack_name(self.id())

        sync_cmd = self.get_sync_command_list(
            template_file=str(template_path),
            stack_name=stack_name,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            s3_bucket=self.s3_bucket.name,
            region=self.region_name,
            parameter_overrides={"Runtime": self._get_python_version()},
        )
        result = run_command_with_input(sync_cmd, "y\n".encode())
        self.assertEqual(result.process.returncode, 0)

        # Cleanup
        self.cfn_client.delete_stack(StackName=stack_name)

    def test_sync_simple_foreach(self):
        """TC-005: Sync simple ForEach template."""
        self._sync_and_verify("language-extensions-simple-foreach")

    def test_sync_nested_foreach(self):
        """Sync nested ForEach (2 levels: env x service)."""
        self._sync_and_verify("language-extensions-nested-foreach")

    def test_sync_dynamodb_streams(self):
        """Sync ForEach with DynamoDB tables and stream processors."""
        self._sync_and_verify("language-extensions-dynamodb")

    def test_sync_sns_topics(self):
        """Sync ForEach with SNS topics and handlers."""
        self._sync_and_verify("language-extensions-sns-topics")
