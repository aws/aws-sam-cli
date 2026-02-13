"""
Integration tests for sam deploy with Language Extensions.
"""

import sys
from pathlib import Path
from unittest import skipIf

import pytest

from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.testing_utils import (
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    run_command,
    get_sam_command,
)

SKIP_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_TESTS, "Skip deploy tests in CI/CD only")
@pytest.mark.python
class TestDeployLanguageExtensions(DeployIntegBase):
    """Integration tests for deploy with Language Extensions."""

    def _get_python_version(self):
        return f"python{sys.version_info.major}.{sys.version_info.minor}"

    def test_deploy_simple_foreach(self):
        """Deploy template with simple ForEach."""
        template_path = self.original_test_data_path.parent.joinpath(
            "buildcmd", "language-extensions-simple-foreach", "template.yaml"
        )
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Build
        build_cmd = [
            get_sam_command(),
            "build",
            "-t",
            str(template_path),
            "--parameter-overrides",
            f"Runtime={self._get_python_version()}",
        ]
        result = run_command(build_cmd)
        self.assertEqual(result.process.returncode, 0)

        # Deploy
        deploy_cmd = self.get_deploy_command_list(
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=stack_name,
            s3_bucket=self.s3_bucket.name,
            region=self.region_name,
            confirm_changeset=False,
        )
        result = run_command(deploy_cmd)
        self.assertEqual(result.process.returncode, 0)

    def test_deploy_dynamic_codeuri(self):
        """Deploy template with dynamic CodeUri."""
        template_path = self.original_test_data_path.parent.joinpath(
            "buildcmd", "language-extensions-dynamic-codeuri", "template.yaml"
        )
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Build
        build_cmd = [
            get_sam_command(),
            "build",
            "-t",
            str(template_path),
            "--parameter-overrides",
            f"Runtime={self._get_python_version()}",
        ]
        result = run_command(build_cmd)
        self.assertEqual(result.process.returncode, 0)

        # Deploy
        deploy_cmd = self.get_deploy_command_list(
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix=stack_name,
            s3_bucket=self.s3_bucket.name,
            region=self.region_name,
            confirm_changeset=False,
        )
        result = run_command(deploy_cmd)
        self.assertEqual(result.process.returncode, 0)
