"""
Integration tests for sam delete with Language Extensions.
"""

import sys
from pathlib import Path
from unittest import skipIf

import pytest

from tests.integration.delete.delete_integ_base import DeleteIntegBase
from tests.testing_utils import (
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    run_command,
    get_sam_command,
)

SKIP_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_TESTS, "Skip delete tests in CI/CD only")
@pytest.mark.python
class TestDeleteLanguageExtensions(DeleteIntegBase):
    """Integration tests for delete with Language Extensions."""

    def _get_python_version(self):
        return f"python{sys.version_info.major}.{sys.version_info.minor}"

    def test_delete_foreach_stack(self):
        """Delete stack with ForEach-generated resources."""
        template_path = self.test_data_path.parent.joinpath(
            "buildcmd", "language-extensions-simple-foreach", "template.yaml"
        )
        stack_name = self._method_to_stack_name(self.id())

        # Deploy stack first
        build_cmd = [
            get_sam_command(),
            "build",
            "-t",
            str(template_path),
            "--parameter-overrides",
            f"Runtime={self._get_python_version()}",
        ]
        run_command(build_cmd)

        deploy_cmd = [
            get_sam_command(),
            "deploy",
            "--stack-name",
            stack_name,
            "--capabilities",
            "CAPABILITY_IAM",
            "--resolve-s3",
            "--region",
            self.region_name,
            "--no-confirm-changeset",
        ]
        result = run_command(deploy_cmd)
        self.assertEqual(result.process.returncode, 0)

        # Delete stack
        delete_cmd = self.get_delete_command_list(
            stack_name=stack_name,
            region=self.region_name,
            no_prompts=True,
        )
        result = run_command(delete_cmd)
        self.assertEqual(result.process.returncode, 0)
