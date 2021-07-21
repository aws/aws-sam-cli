import os
import pathlib
import re
import shutil
import logging

from subprocess import Popen, PIPE, TimeoutExpired
import tempfile

from unittest import skipIf
from parameterized import parameterized, param

import docker

from samcli.lib.utils.hash import dir_checksum, file_checksum
from samcli.lib.warnings.sam_cli_warning import CodeDeployWarning
from .package_integ_base import CdkPackageIntegPythonBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY, run_command

# Package tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master and tests are not run by Canary.
SKIP_PACKAGE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
TIMEOUT = 300
LOG = logging.getLogger(__name__)


@skipIf(SKIP_PACKAGE_TESTS, "Skip package tests in CI/CD only")
class TestPackageCdkPythonImage(CdkPackageIntegPythonBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("alpine", "latest"),
        ]
        # setup some images locally by pulling them
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
        super().setUpClass()

    @parameterized.expand(
        [
            "aws-lambda-function-image",
        ]
    )
    def test_package_template_without_image_repository(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        command_list = self.get_command_list(
            cdk_app=os.path.join(self.working_dir, ".aws-sam", "build"),
        )
        LOG.debug("command list: %s", command_list)
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(2, process_execute.process.returncode)
        self.assertIn("Error: Missing option '--image-repository'", process_execute.stderr.decode("utf-8"))

    @parameterized.expand(
        [
            "aws-lambda-function-image",
        ]
    )
    def test_package_template_with_image_repository(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        command_list = self.get_command_list(
            image_repository=self.ecr_repo_name,
            cdk_app=os.path.join(self.working_dir, ".aws-sam", "build"),
        )
        LOG.debug("command list: %s", command_list)
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(0, process_execute.process.returncode)
        self.assertIn(f"{self.ecr_repo_name}", process_execute.stdout.decode("utf-8"))

    @parameterized.expand(
        [
            ("lambda-function", "aws-lambda-function-image"),
        ]
    )
    def test_package_template_with_image_repositories(self, resource_id, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        command_list = self.get_command_list(
            image_repositories=f"{resource_id}={self.ecr_repo_name}",
            cdk_app=os.path.join(self.working_dir, ".aws-sam", "build"),
        )
        LOG.debug("command list: %s", command_list)
        process_execute = run_command(command_list, cwd=self.working_dir)

        LOG.debug(process_execute.stdout.decode("utf-8"))
        self.assertEqual(0, process_execute.process.returncode)
        self.assertIn(f"{self.ecr_repo_name}", process_execute.stdout.decode("utf-8"))

    @parameterized.expand(
        [
            "aws-lambda-function-image",
        ]
    )
    def test_package_template_with_non_ecr_repo_uri_image_repository(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        command_list = self.get_command_list(
            image_repository="non-ecr-repo-uri",
            resolve_s3=True,
            cdk_app=os.path.join(self.working_dir, ".aws-sam", "build"),
        )
        LOG.debug("command list: %s", command_list)
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(2, process_execute.process.returncode)
        self.assertIn("Error: Invalid value for '--image-repository'", process_execute.stderr.decode("utf-8"))

    @parameterized.expand(
        [
            "aws-lambda-function-image",
        ]
    )
    def test_package_template_and_s3_bucket(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket,
            cdk_app=os.path.join(self.working_dir, ".aws-sam", "build"),
        )
        LOG.debug("command list: %s", command_list)
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(2, process_execute.process.returncode)
        self.assertIn("Error: Missing option '--image-repository'", process_execute.stderr.decode("utf-8"))
