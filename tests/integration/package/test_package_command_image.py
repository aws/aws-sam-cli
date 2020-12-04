from subprocess import Popen, PIPE, TimeoutExpired

from unittest import skipIf
from parameterized import parameterized

import docker

from .package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Package tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master and tests are not run by Canary.
SKIP_PACKAGE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
TIMEOUT = 300


@skipIf(SKIP_PACKAGE_TESTS, "Skip package tests in CI/CD only")
class TestPackageImage(PackageIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [("alpine", "latest")]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
        super(TestPackageImage, cls).setUpClass()

    def setUp(self):
        super(TestPackageImage, self).setUp()

    def tearDown(self):
        super(TestPackageImage, self).tearDown()

    @parameterized.expand(["aws-serverless-function-image.yaml", "aws-lambda-function-image.yaml"])
    def test_package_template_without_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(template=template_path)

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()

        self.assertIn("Error: Missing option '--image-repository'", process_stderr.decode("utf-8"))
        self.assertEqual(2, process.returncode)

    @parameterized.expand(["aws-serverless-function-image.yaml", "aws-lambda-function-image.yaml"])
    def test_package_template_with_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            image_repository=self.ecr_repo_name, template=template_path, resolve_s3=True
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()

        self.assertIn(f"{self.ecr_repo_name}", process_stdout.decode("utf-8"))
        self.assertEqual(0, process.returncode)

    @parameterized.expand(["aws-serverless-function-image.yaml", "aws-lambda-function-image.yaml"])
    def test_package_template_with_non_ecr_repo_uri_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            image_repository="non-ecr-repo-uri", template=template_path, resolve_s3=True
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()

        self.assertEqual(2, process.returncode)
        self.assertIn("Error: Invalid value for '--image-repository'", process_stderr.decode("utf-8"))

    @parameterized.expand(["aws-serverless-function-image.yaml", "aws-lambda-function-image.yaml"])
    def test_package_template_and_s3_bucket(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(s3_bucket=self.s3_bucket, template=template_path)

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()

        self.assertEqual(2, process.returncode)
        self.assertIn("Error: Missing option '--image-repository'", process_stderr.decode("utf-8"))
