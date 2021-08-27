import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from unittest import skipIf
import boto3
import docker
from botocore.config import Config
from parameterized import parameterized
from botocore.exceptions import ClientError

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.delete.delete_integ_base import DeleteIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

# Delete tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DELETE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
TIMEOUT = 300
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_DELETE_TESTS, "Skip delete tests in CI/CD only")
class TestDelete(PackageIntegBase, DeployIntegBase, DeleteIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("alpine", "latest"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)

        PackageIntegBase.setUpClass()
        DeployIntegBase.setUpClass()
        DeleteIntegBase.setUpClass()

    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        self.sns_arn = os.environ.get("AWS_SNS")
        time.sleep(CFN_SLEEP)
        super().setUp()

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
        ]
    )
    def test_delete_no_prompts_with_s3_prefix_present_image(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        config_file_name = stack_name + ".toml"
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            guided=False,
            config_file=config_file_name,
            image_repository=self.ecr_repo_name,
            stack_name=stack_name,
            resolve_s3=True,
            capabilities="CAPABILITY_IAM",
        )

        deploy_process_execute = run_command(deploy_command_list)

        self.assertEqual(deploy_process_execute.process.returncode, 0)

        config_file_path = self.test_data_path.joinpath(config_file_name)
        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, config_file=config_file_path, region="us-east-1", no_prompts=True
        )

        delete_process_execute = run_command(delete_command_list)
        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

        # Remove the local config file created
        if os.path.isfile(config_file_path):
            os.remove(config_file_path)

    # TODO: Add 3 more tests after Auto ECR is merged to develop
    # 1. Create a stack using guided deploy of type image and delete
    # 2. Delete the ECR Companion Stack as input stack.
    # 3. Retain ECR Repository that contains atleast 1 image.
    #    - Create a stack using guided deploy of type image
    #    - Select no for deleting ECR repository and this will retain the non-empty repository

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"
