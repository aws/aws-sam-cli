"""
Integration tests for sam logs with Language Extensions.
"""

import sys
import os
from pathlib import Path
from unittest import skipIf

import pytest

from tests.integration.logs.logs_integ_base import LogsIntegBase
from tests.testing_utils import (
    run_command,
    get_sam_command,
)


@pytest.mark.python
class TestLogsLanguageExtensions(LogsIntegBase):
    """Integration tests for logs with Language Extensions."""

    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "logs")

    def _get_python_version(self):
        return f"python{sys.version_info.major}.{sys.version_info.minor}"

    def test_logs_foreach_function(self):
        """TC-006: Get logs from ForEach-generated function."""
        template_path = self.test_data_path.parent.joinpath(
            "buildcmd", "language-extensions-simple-foreach", "template.yaml"
        )
        stack_name = f"test-logs-lang-ext-{id(self)}"

        try:
            # Deploy stack
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

            # Get logs (may be empty but command should work)
            logs_cmd = self.get_logs_command_list(
                stack_name=stack_name,
                name="AlphaFunction",
            )
            result = run_command(logs_cmd)
            self.assertEqual(result.process.returncode, 0)

        finally:
            # Cleanup
            delete_cmd = [
                get_sam_command(),
                "delete",
                "--stack-name",
                stack_name,
                "--region",
                self.region_name,
                "--no-prompts",
            ]
            run_command(delete_cmd)
