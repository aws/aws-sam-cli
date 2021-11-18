import os

import click
from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack
import shutil
import time
import pytest
from unittest.mock import patch
from pathlib import Path
from unittest import skipIf

from io import StringIO

import boto3
from botocore.exceptions import ClientError
import docker
from botocore.config import Config
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase

from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_SYNC_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_SYNC_TESTS, "Skip sync tests in CI/CD only")
class TestSync(BuildIntegBase, SyncIntegBase, PackageIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("public.ecr.aws/sam/emulation-python3.7", "latest"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
            cls.docker_client.api.tag(f"{repo}:{tag}", "emulation-python3.7", tag="latest")
            cls.docker_client.api.tag(f"{repo}:{tag}", "emulation-python3.7-2", tag="latest")

        # setup signing profile arn & name
        cls.signing_profile_name = os.environ.get("AWS_SIGNING_PROFILE_NAME")
        cls.signing_profile_version_arn = os.environ.get("AWS_SIGNING_PROFILE_VERSION_ARN")

        PackageIntegBase.setUpClass()

        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "sync")

    def setUp(self):
        self.cfn_client = boto3.client("cloudformation")
        self.ecr_client = boto3.client("ecr")
        self.lambda_client = boto3.client("lambda")
        self.api_client = boto3.client("apigateway")
        self.sns_arn = os.environ.get("AWS_SNS")
        self.stacks = []
        time.sleep(CFN_SLEEP)
        super().setUp()

    def tearDown(self):
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "build"), ignore_errors=True)
        for stack in self.stacks:
            # because of the termination protection, do not delete aws-sam-cli-managed-default stack
            stack_name = stack["name"]
            if stack_name != SAM_CLI_STACK_NAME:
                region = stack.get("region")
                cfn_client = (
                    self.cfn_client if not region else boto3.client("cloudformation", config=Config(region_name=region))
                )
                ecr_client = self.ecr_client if not region else boto3.client("ecr", config=Config(region_name=region))
                self._delete_companion_stack(cfn_client, ecr_client, self._stack_name_to_companion_stack(stack_name))
                cfn_client.delete_stack(StackName=stack_name)
        super().tearDown()

    @pytest.fixture(autouse=True)
    def shared_stack(self):
        template_path = str(self.test_data_path.joinpath("template.yaml"))
        stack_name = self._method_to_stack_name(self.id())

        yield stack_name

        # Run infra sync
        # sync_command_list = self.get_sync_command_list(
        #     template_file=template_path,
        #     code=False,
        #     watch=False,
        #     resource_id=None,
        #     resource=None,
        #     dependency_layer=True,
        #     stack_name=stack_name,
        #     region=None,
        #     profile=None,
        #     parameter_overrides="Parameter=Clarity",
        #     base_dir=None,
        #     image_repository=self.ecr_repo_name,
        #     image_repositories=None,
        #     s3_prefix="integ_deploy",
        #     kms_key_id=self.kms_key,
        #     capabilities=None,
        #     capabilities_list=None,
        #     role_arn=None,
        #     notification_arns=None,
        #     tags="integ=true clarity=yes foo_bar=baz",
        #     metadata=None,
        # )

        # run_command_with_input(sync_command_list, "y\n".encode())
        # yield stack_name
        # cfn_client = boto3.client("cloudformation")
        # ecr_client = boto3.client("ecr")
        # self._delete_companion_stack(cfn_client, ecr_client, self._stack_name_to_companion_stack(stack_name))
        # cfn_client.delete_stack(StackName=stack_name)

    # @parameterized.expand(["template.yaml"])
    def test_sync_infra(self, shared_stack):
        print(shared_stack)

        self.assertEqual(shared_stack, shared_stack)

        # template_path = str(self.test_data_path.joinpath(template_file))
        # stack_name = self._method_to_stack_name(self.id())
        # self.stacks.append({"name": stack_name})

        # # Run infra sync
        # sync_command_list = self.get_sync_command_list(
        #     template_file=template_path,
        #     code=False,
        #     watch=False,
        #     resource_id=None,
        #     resource=None,
        #     dependency_layer=True,
        #     stack_name=stack_name,
        #     region=None,
        #     profile=None,
        #     parameter_overrides="Parameter=Clarity",
        #     base_dir=None,
        #     image_repository=self.ecr_repo_name,
        #     image_repositories=None,
        #     s3_prefix="integ_deploy",
        #     kms_key_id=self.kms_key,
        #     capabilities=None,
        #     capabilities_list=None,
        #     role_arn=None,
        #     notification_arns=None,
        #     tags="integ=true clarity=yes foo_bar=baz",
        #     metadata=None,
        # )

        # sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        # self.assertEqual(sync_process_execute.process.returncode, 0)
        # self.assertIn("Stack creation succeeded. Sync infra completed.", str(sync_process_execute.stderr))

        # Lambda api call here


    @parameterized.expand(["template.yaml"])
    def test_sync_infra_no_confirm(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            resource_id=None,
            resource=None,
            dependency_layer=True,
            stack_name=stack_name,
            region=None,
            profile=None,
            parameter_overrides="Parameter=Clarity",
            base_dir=None,
            image_repository=self.ecr_repo_name,
            image_repositories=None,
            s3_prefix="integ_deploy",
            kms_key_id=self.kms_key,
            capabilities=None,
            capabilities_list=None,
            role_arn=None,
            notification_arns=None,
            tags="integ=true clarity=yes foo_bar=baz",
            metadata=None,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "n\n".encode())

        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertNotIn("Build Succeeded", str(sync_process_execute.stderr))

    @parameterized.expand(["template.yaml"])
    def test_sync_infra_no_stack_name(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            resource_id=None,
            resource=None,
            dependency_layer=True,
            stack_name=None,
            region=None,
            profile=None,
            parameter_overrides="Parameter=Clarity",
            base_dir=None,
            image_repository=self.ecr_repo_name,
            image_repositories=None,
            s3_prefix="integ_deploy",
            kms_key_id=self.kms_key,
            capabilities=None,
            capabilities_list=None,
            role_arn=None,
            notification_arns=None,
            tags="integ=true clarity=yes foo_bar=baz",
            metadata=None,
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 2)
        self.assertIn("Error: Missing option '--stack-name'.", str(sync_process_execute.stderr))

    @parameterized.expand(["template.yaml"])
    def test_sync_infra_no_capabilities(self, template_file):
        template_path = str(self.test_data_path.joinpath(template_file))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Run infra sync
        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            code=False,
            watch=False,
            resource_id=None,
            resource=None,
            dependency_layer=True,
            stack_name=stack_name,
            region=None,
            profile=None,
            parameter_overrides="Parameter=Clarity",
            base_dir=None,
            image_repository=self.ecr_repo_name,
            image_repositories=None,
            s3_prefix="integ_deploy",
            kms_key_id=self.kms_key,
            capabilities="CAPABILITY_IAM",
            capabilities_list=None,
            role_arn=None,
            notification_arns=None,
            tags="integ=true clarity=yes foo_bar=baz",
            metadata=None,
        )

        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 1)
        self.assertIn(
            "An error occurred (InsufficientCapabilitiesException) when calling the CreateStack operation: \
Requires capabilities : [CAPABILITY_AUTO_EXPAND]",
            str(sync_process_execute.stderr),
        )

    # @parameterized.expand(["template.yaml"])
    # def test_sync_infra_no_image_repo(self, template_file):
    #     template_path = str(self.test_data_path.joinpath(template_file))
    #     stack_name = self._method_to_stack_name(self.id())

    #     # Run infra sync
    #     sync_command_list = self.get_sync_command_list(
    #         template_file=template_path,
    #         code=False,
    #         watch=False,
    #         resource_id=None,
    #         resource=None,
    #         dependency_layer=True,
    #         stack_name=stack_name,
    #         region=None,
    #         profile=None,
    #         parameter_overrides="Parameter=Clarity",
    #         base_dir=None,
    #         image_repository=None,
    #         image_repositories=None,
    #         s3_prefix="integ_deploy",
    #         kms_key_id=self.kms_key,
    #         capabilities=None,
    #         capabilities_list=None,
    #         role_arn=None,
    #         notification_arns=None,
    #         tags="integ=true clarity=yes foo_bar=baz",
    #         metadata=None,
    #     )

    #     sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
    #     self.assertEqual(sync_process_execute.process.returncode, 2)
    #     self.assertIn("", str(sync_process_execute.stderr))

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"

    def _stack_name_to_companion_stack(self, stack_name):
        return CompanionStack(stack_name).stack_name

    def _delete_companion_stack(self, cfn_client, ecr_client, companion_stack_name):
        repos = list()
        try:
            cfn_client.describe_stacks(StackName=companion_stack_name)
        except ClientError:
            return
        stack = boto3.resource("cloudformation").Stack(companion_stack_name)
        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::ECR::Repository":
                repos.append(resource.physical_resource_id)
        for repo in repos:
            try:
                ecr_client.delete_repository(repositoryName=repo, force=True)
            except ecr_client.exceptions.RepositoryNotFoundException:
                pass
        cfn_client.delete_stack(StackName=companion_stack_name)
