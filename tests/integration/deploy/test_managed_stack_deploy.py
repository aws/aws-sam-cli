import os
from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from unittest import skipIf

import boto3
from botocore.exceptions import ClientError
import docker
from botocore.config import Config
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
TIMEOUT = 300
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_DEPLOY_TESTS, "Skip deploy tests in CI/CD only")
class TestManagedStackDeploy(PackageIntegBase, DeployIntegBase):
    @classmethod
    def setUpClass(cls):
        PackageIntegBase.setUpClass()
        DeployIntegBase.setUpClass()

    def setUp(self):
        self.cfn_client = boto3.client("cloudformation")
        self.s3_client = boto3.client("s3")
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
                cfn_client.delete_stack(StackName=stack_name)
        super().tearDown()

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_managed_stack_creation_resolve_s3(self, template_file):
        self._delete_managed_stack(self.cfn_client, self.s3_client)
        self.assertFalse(self._does_stack_exist(self.cfn_client, SAM_CLI_STACK_NAME))

        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            resolve_s3=True,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self._managed_stack_sanity_check(self.cfn_client, self.s3_client)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_managed_stack_creation_guided(self, template_file):
        self._delete_managed_stack(self.cfn_client, self.s3_client)
        self.assertFalse(self._does_stack_exist(self.cfn_client, SAM_CLI_STACK_NAME))
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))
        self._managed_stack_sanity_check(self.cfn_client, self.s3_client)

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"

    def _delete_managed_stack(self, cfn_client, s3_client, wait=True):
        if not self._does_stack_exist(cfn_client, SAM_CLI_STACK_NAME):
            return

        stack = boto3.resource("cloudformation").Stack(SAM_CLI_STACK_NAME)
        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::S3::Bucket":
                s3_bucket_name = resource.physical_resource_id

        if s3_bucket_name:
            s3 = boto3.resource("s3")
            bucket = s3.Bucket(s3_bucket_name)
            bucket.object_versions.delete()
            s3_client.delete_bucket(Bucket=s3_bucket_name)
        cfn_client.delete_stack(StackName=SAM_CLI_STACK_NAME)

        if wait:
            waiter = cfn_client.get_waiter("stack_delete_complete")
            waiter_config = {"Delay": 15, "MaxAttempts": 120}
            waiter.wait(StackName=SAM_CLI_STACK_NAME, WaiterConfig=waiter_config)

    def _managed_stack_sanity_check(self, cfn_client, s3_client):
        if not self._does_stack_exist(cfn_client, SAM_CLI_STACK_NAME):
            raise ManagedStackError("Managed stack does not exist")

        stack = boto3.resource("cloudformation").Stack(SAM_CLI_STACK_NAME)

        if stack.stack_status not in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
            raise ManagedStackError("Managed stack status is not in CREATE_COMPLETE or UPDATE_COMPLETE")

        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::S3::Bucket":
                s3_bucket_name = resource.physical_resource_id

        if not s3_bucket_name:
            raise ManagedStackError("Managed stack does not have S3 bucket")

        s3 = boto3.resource("s3")
        if s3.Bucket(s3_bucket_name) not in s3.buckets.all():
            raise ManagedStackError("Managed stack S3 bucket does not exist")

    def _does_stack_exist(self, cfn_client, stack_name):
        try:
            cfn_client.describe_stacks(StackName=stack_name)
            return True
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message")
            if error_message == f"Stack with id {stack_name} does not exist":
                return False
            raise e


class ManagedStackError(Exception):
    pass
