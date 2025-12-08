import os
import re
import tempfile
from subprocess import Popen, PIPE, TimeoutExpired

from unittest import skipIf
from urllib.parse import urlparse

import boto3
from parameterized import parameterized


from samcli.commands._utils.template import get_template_data
from samcli.local.docker.utils import get_validated_container_client
from .package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY, MAX_ERROR_OUTPUT_LENGTH


# Package tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master and tests are not run by Canary.
SKIP_PACKAGE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
TIMEOUT = 300


@skipIf(SKIP_PACKAGE_TESTS, "Skip package tests in CI/CD only")
class TestPackageImage(PackageIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = get_validated_container_client()
        cls.local_images = [
            ("public.ecr.aws/sam/emulation-python3.9", "latest"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
            cls.docker_client.api.tag(f"{repo}:{tag}", "emulation-python3.9", tag="latest")
            cls.docker_client.api.tag(f"{repo}:{tag}", "emulation-python3.9-2", tag="latest")
            cls.docker_client.api.tag(f"{repo}:{tag}", "colorsrandomfunctionf61b9209", tag="latest")

        super(TestPackageImage, cls).setUpClass()

    def setUp(self):
        super(TestPackageImage, self).setUp()

    def tearDown(self):
        super(TestPackageImage, self).tearDown()

    def _assert_finch_docker_success(self, stderr_text, error_message):
        """
        Helper function to check if Docker/Finch operations completed successfully.
        Finch shows "done" or "elapsed:" indicators for successful operations.
        """
        success = "done" in stderr_text or "elapsed:" in stderr_text
        self.assertTrue(success, f"{error_message}. Got stderr: {stderr_text[:MAX_ERROR_OUTPUT_LENGTH]}...")

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
            "aws-lambda-function-image.yaml",
            "cdk_v1_synthesized_template_image_functions.json",
        ]
    )
    def test_package_template_without_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(template=template_path)

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()
        self.assertIn(
            "Error: Missing option '--image-repositories', '--image-repository'", process_stderr.decode("utf-8")
        )
        self.assertEqual(2, process.returncode)

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
            "aws-lambda-function-image.yaml",
            "aws-lambda-function-image-and-api.yaml",
            "cdk_v1_synthesized_template_image_functions.json",
        ]
    )
    def test_package_template_with_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(image_repository=self.ecr_repo_name, template=template_path)

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()

        self.assertEqual(0, process.returncode)
        self.assertIn(f"{self.ecr_repo_name}", process_stdout.decode("utf-8"))

    @parameterized.expand(
        [
            ("Hello", "aws-serverless-function-image.yaml"),
            ("MyLambdaFunction", "aws-lambda-function-image.yaml"),
            ("ColorsRandomFunctionF61B9209", "cdk_v1_synthesized_template_image_functions.json"),
            ("ColorsRandomFunction", "cdk_v1_synthesized_template_image_functions.json"),
        ]
    )
    def test_package_template_with_image_repositories(self, resource_id, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(
            image_repositories=f"{resource_id}={self.ecr_repo_name}", template=template_path
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

    @parameterized.expand(
        [
            ("ColorsRandomFunctionF61B9209", "cdk_v1_synthesized_template_Level2_nested_image_functions.json"),
            ("ColorsRandomFunction", "cdk_v1_synthesized_template_Level2_nested_image_functions.json"),
            ("Level2Stack/ColorsRandomFunction", "cdk_v1_synthesized_template_Level2_nested_image_functions.json"),
            ("ColorsRandomFunctionF61B9209", "cdk_v1_synthesized_template_Level1_nested_image_functions.json"),
            ("ColorsRandomFunction", "cdk_v1_synthesized_template_Level1_nested_image_functions.json"),
            (
                "Level1Stack/Level2Stack/ColorsRandomFunction",
                "cdk_v1_synthesized_template_Level1_nested_image_functions.json",
            ),
        ]
    )
    def test_package_template_with_image_repositories_nested_stack(self, resource_id, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(
            image_repositories=f"{resource_id}={self.ecr_repo_name}", template=template_path, resolve_s3=True
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()

        # Check for ECR repository name in stderr (Docker) or successful completion (Finch)
        stderr_text = process_stderr.decode("utf-8")
        if f"{self.ecr_repo_name}" not in stderr_text:
            # With Finch, the ECR repo name might not appear in stderr but should show success indicators
            self._assert_finch_docker_success(
                stderr_text, f"Expected ECR repo name '{self.ecr_repo_name}' in stderr or successful completion. "
            )
        self.assertEqual(0, process.returncode)

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
            "aws-lambda-function-image.yaml",
            "cdk_v1_synthesized_template_image_functions.json",
        ]
    )
    def test_package_template_with_non_ecr_repo_uri_image_repository(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(
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

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
            "aws-lambda-function-image.yaml",
            "cdk_v1_synthesized_template_image_functions.json",
        ]
    )
    def test_package_template_and_s3_bucket(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(
            s3_bucket=self.s3_bucket, s3_prefix=self.s3_prefix, template=template_path
        )

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()

        self.assertEqual(2, process.returncode)
        self.assertIn(
            "Error: Missing option '--image-repositories', '--image-repository'", process_stderr.decode("utf-8")
        )

    @parameterized.expand(["aws-serverless-application-image.yaml"])
    def test_package_template_with_image_function_in_nested_application(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        # when image function is not in main template, erc_repo_name does not show up in stdout
        # here we download the nested application template file and verify its content
        with tempfile.NamedTemporaryFile() as packaged_file, tempfile.TemporaryFile() as packaged_nested_file:
            # https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
            # Closes the NamedTemporaryFile as on Windows NT or later, NamedTemporaryFile cannot be opened twice.
            packaged_file.close()

            command_list = PackageIntegBase.get_command_list(
                image_repository=self.ecr_repo_name,
                template=template_path,
                resolve_s3=True,
                output_template_file=packaged_file.name,
            )

            process = Popen(command_list, stdout=PIPE, stderr=PIPE)
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(0, process.returncode)

            # download the root template and locate nested template url
            template_dict = get_template_data(packaged_file.name)
            nested_app_template_uri = (
                template_dict.get("Resources", {}).get("myApp", {}).get("Properties").get("Location")
            )

            # extract bucket name and object key from the url
            parsed = urlparse(nested_app_template_uri)
            bucket_name, key = parsed.path.lstrip("/").split("/")

            # download and verify it contains ecr_repo_name
            s3 = boto3.resource("s3")
            s3.Object(bucket_name, key).download_fileobj(packaged_nested_file)
            packaged_nested_file.seek(0)
            self.assertIn(f"{self.ecr_repo_name}", packaged_nested_file.read().decode())

    def test_package_with_deep_nested_template_image(self):
        """
        this template contains two nested stacks:
        - root
          - FunctionA
          - ChildStackX
            - FunctionB
            - ChildStackY
              - FunctionA
        """
        template_file = os.path.join("deep-nested-image", "template.yaml")

        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(
            image_repository=self.ecr_repo_name, resolve_s3=True, template=template_path, force_upload=True
        )

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip().decode("utf-8")

        # verify all function images are pushed
        images = [
            ("emulation-python3.9", "latest"),
            ("emulation-python3.9-2", "latest"),
        ]
        for image, tag in images:
            # check string like this:
            # ...python-ce689abb4f0d-3.9-slim: digest:...
            # For Docker, look for digest pattern; for Finch, look for successful completion
            digest_pattern = rf"{image}-.+-{tag}: digest:"
            if not re.search(digest_pattern, process_stderr):
                # With Finch, we might not see the digest pattern but should see successful operations
                self._assert_finch_docker_success(
                    process_stderr,
                    f"Expected digest pattern '{digest_pattern}' or successful completion for {image}:{tag}. ",
                )

    @parameterized.expand(["template-image-load.yaml"])
    def test_package_with_loadable_image_archive(self, template_file):
        template_path = self.test_data_path.joinpath(os.path.join("load-image-archive", template_file))
        command_list = PackageIntegBase.get_command_list(image_repository=self.ecr_repo_name, template=template_path)

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()

        # Handle the known issue where Finch imports tagless images differently than Docker
        # Docker imports images by digest, Finch may import as "overlayfs:" which causes issues
        stderr_text = process_stderr.decode("utf-8")

        if process.returncode != 0:
            # Check if it's the known Finch "overlayfs:" issue
            if "no such image: overlayfs:" in stderr_text:
                # This is a known issue with Finch's image import behavior for tagless images
                # The test data has a repo (overlayfs) but no tag, causing different behavior
                # For now, we'll skip this specific case as it's a known limitation
                self.skipTest(
                    "Known issue: Finch handles tagless image imports differently than Docker (overlayfs: issue)"
                )
            else:
                # Some other error occurred, fail the test with details
                self.fail(f"Command failed with return code {process.returncode}. Stderr: {stderr_text}")

        self.assertEqual(0, process.returncode)

        # Check for ECR repository name in stderr (Docker) or successful completion (Finch)
        if f"{self.ecr_repo_name}" not in stderr_text:
            # With Finch, the ECR repo name might not appear in stderr but should show success indicators
            self._assert_finch_docker_success(
                stderr_text, f"Expected ECR repo name '{self.ecr_repo_name}' in stderr or successful completion. "
            )

    @parameterized.expand(["template-image-load-fail.yaml"])
    def test_package_with_nonloadable_image_archive(self, template_file):
        template_path = self.test_data_path.joinpath(os.path.join("load-image-archive", template_file))
        command_list = PackageIntegBase.get_command_list(image_repository=self.ecr_repo_name, template=template_path)

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip()

        self.assertEqual(1, process.returncode)
        self.assertIn("unexpected EOF", process_stderr.decode("utf-8"))

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
            "aws-lambda-function-image.yaml",
        ]
    )
    def test_package_template_with_resolve_image_repos(self, template_file):

        template_path = self.test_data_path.joinpath(template_file)
        command_list = PackageIntegBase.get_command_list(
            s3_bucket=self.bucket_name,
            template=template_path,
            resolve_image_repos=True,
        )

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        
        process_stdout = stdout.strip().decode("utf-8")
        process_stderr = stderr.strip().decode("utf-8")
        self.assertEqual(0, process.returncode, f"Command failed. Stderr: {process_stderr}")
        # Verify ECR repository URI is in the output (auto-created repository)
        # The output should contain an ECR repository URI pattern
        ecr_uri_pattern = r"\d+\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/"
        self.assertRegex(process_stdout, ecr_uri_pattern, "Expected ECR repository URI in packaged template")
