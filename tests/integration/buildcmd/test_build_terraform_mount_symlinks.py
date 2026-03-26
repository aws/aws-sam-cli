"""
End-to-end integration tests for --mount-symlinks with Terraform hook builds.

Tests that `sam build --hook-name terraform --mount-symlinks` correctly passes
the mount_symlinks flag through to the copy_terraform_built_artifacts.py script,
allowing zip artifacts containing symlinks to be extracted successfully.
"""

import logging
import os
import shutil
from pathlib import Path
from unittest import TestCase, skipIf

import pytest

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import IS_WINDOWS, run_command, get_sam_command

LOG = logging.getLogger(__name__)

CI_OVERRIDE = os.environ.get("CODEBUILD_CI_OVERRIDE", False)
RUN_BY_CANARY = os.environ.get("BY_CANARY", False)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformWithSymlinkZip(BuildIntegBase):
    """Test sam build --hook-name terraform with a zip artifact containing symlinks."""

    terraform_application = Path("terraform/zip_with_symlink")
    template = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.terraform_application_path = str(Path(cls.test_data_path, cls.terraform_application))

    def setUp(self):
        super().setUp()
        shutil.copytree(Path(self.terraform_application_path), Path(self.working_dir), dirs_exist_ok=True)

    def _run_build(self, mount_symlinks=False):
        """Run sam build --hook-name terraform, optionally with --mount-symlinks."""
        build_cmd = self.get_command_list(
            function_identifier="aws_lambda_function.symlink_function",
            hook_name="terraform",
            mount_symlinks=mount_symlinks,
        )
        LOG.info("Running: %s", " ".join(build_cmd))
        result = run_command(build_cmd, cwd=self.working_dir)
        stdout = result.stdout.decode("utf-8") if isinstance(result.stdout, bytes) else result.stdout
        stderr = result.stderr.decode("utf-8") if isinstance(result.stderr, bytes) else result.stderr
        return stdout, stderr, result.process.returncode

    def test_build_fails_without_mount_symlinks(self):
        """Build should fail when zip contains absolute symlink and --mount-symlinks is not set."""
        _, stderr, returncode = self._run_build(mount_symlinks=False)
        self.assertNotEqual(returncode, 0, f"Expected build to fail but it succeeded. stderr: {stderr}")
        self.assertIn(
            "Failed to extract file from the zip file. A symlink has an absolute target which is not allowed",
            stderr,
        )

    def test_build_succeeds_with_mount_symlinks(self):
        """Build should succeed when zip contains absolute symlink and --mount-symlinks is set."""
        _, stderr, returncode = self._run_build(mount_symlinks=True)
        self.assertEqual(returncode, 0, f"Expected build to succeed but it failed. stderr: {stderr}")

        # Find the function build directory (SAM CLI generates a hashed logical ID)
        build_dir = Path(self.working_dir) / ".aws-sam" / "build"
        self.assertTrue(build_dir.exists(), f"Build output directory not found: {build_dir}")
        function_dirs = [d for d in build_dir.iterdir() if d.is_dir()]
        self.assertEqual(len(function_dirs), 1, f"Expected 1 function dir, found: {function_dirs}")

        function_dir = function_dirs[0]
        symlink_path = function_dir / "external_link"
        self.assertTrue(symlink_path.is_symlink(), f"Expected symlink at {symlink_path}")
        self.assertEqual(os.readlink(str(symlink_path)), "/tmp/some_external_target")
