import os
import shutil
import time
from unittest import skipIf

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from parameterized import parameterized

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

PYTHON_VERSION = os.environ.get("PYTHON_VERSION", "0.0.0")

# Managed stack tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_MANAGED_STACK_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
# Limits the managed stack tests to be run on a single python version to avoid CI race conditions
IS_TARGETTED_PYTHON_VERSION = PYTHON_VERSION.startswith("3.6")

CFN_PYTHON_VERSION_SUFFIX = PYTHON_VERSION.replace(".", "-")
CFN_SLEEP = 3
# Set region for managed stacks to be in a different region than the ones in deploy
DEFAULT_REGION = "us-west-2"


@skipIf(SKIP_MANAGED_STACK_TESTS or not IS_TARGETTED_PYTHON_VERSION, "Skip managed stack tests in CI/CD only")
class TestManagedStackDeploy(PackageIntegBase, DeployIntegBase):
    @classmethod
    def setUpClass(cls):
        PackageIntegBase.setUpClass()
        DeployIntegBase.setUpClass()

    def setUp(self):
        self.cfn_client = boto3.client("cloudformation", region_name=DEFAULT_REGION)
        self.s3_client = boto3.client("s3", region_name=DEFAULT_REGION)
        self.sns_arn = os.environ.get("AWS_SNS")
        self.stacks = []
        time.sleep(CFN_SLEEP)

        self._delete_managed_stack(self.cfn_client, self.s3_client, DEFAULT_REGION)
        self.assertFalse(self._does_stack_exist(self.cfn_client, SAM_CLI_STACK_NAME))

        super().setUp()

    def tearDown(self):
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "build"), ignore_errors=True)
        for stack in self.stacks:
            stack_name = stack["name"]
            if stack_name != SAM_CLI_STACK_NAME:
                region = stack.get("region") or DEFAULT_REGION
                cfn_client = (
                    self.cfn_client if not region else boto3.client("cloudformation", config=Config(region_name=region))
                )
                cfn_client.delete_stack(StackName=stack_name)

        self._delete_managed_stack(self.cfn_client, self.s3_client, DEFAULT_REGION)
        self.assertFalse(self._does_stack_exist(self.cfn_client, SAM_CLI_STACK_NAME))
        super().tearDown()

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_managed_stack_creation_resolve_s3(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            force_upload=True,
            parameter_overrides="Parameter=Clarity",
            tags="integ=true clarity=yes foo_bar=baz",
            resolve_s3=True,
            region=DEFAULT_REGION,
        )

        deploy_process_execute = run_command(deploy_command_list)
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self._managed_stack_sanity_check(self.cfn_client, self.s3_client, DEFAULT_REGION)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_managed_stack_creation_guided(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, region=DEFAULT_REGION, guided=True
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.process.returncode, 0)
        self.stacks.append({"name": SAM_CLI_STACK_NAME})
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))
        self._managed_stack_sanity_check(self.cfn_client, self.s3_client, DEFAULT_REGION)

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"

    def _delete_managed_stack(self, cfn_client, s3_client, region, wait=True):
        if not self._does_stack_exist(cfn_client, SAM_CLI_STACK_NAME):
            return

        stack = boto3.resource("cloudformation", region_name=region).Stack(SAM_CLI_STACK_NAME)
        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::S3::Bucket":
                s3_bucket_name = resource.physical_resource_id

        if s3_bucket_name:
            s3 = boto3.resource("s3", region_name=region)
            bucket = s3.Bucket(s3_bucket_name)
            bucket.object_versions.delete()
            s3_client.delete_bucket(Bucket=s3_bucket_name)
        cfn_client.delete_stack(StackName=SAM_CLI_STACK_NAME)

        if wait:
            waiter = cfn_client.get_waiter("stack_delete_complete")
            waiter_config = {"Delay": 15, "MaxAttempts": 120}
            waiter.wait(StackName=SAM_CLI_STACK_NAME, WaiterConfig=waiter_config)

    def _managed_stack_sanity_check(self, cfn_client, s3_client, region):
        if not self._does_stack_exist(cfn_client, SAM_CLI_STACK_NAME):
            raise ManagedStackError("Managed stack does not exist")

        stack = boto3.resource("cloudformation", region_name=region).Stack(SAM_CLI_STACK_NAME)

        if stack.stack_status not in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
            raise ManagedStackError("Managed stack status is not in CREATE_COMPLETE or UPDATE_COMPLETE")

        resources = stack.resource_summaries.all()
        for resource in resources:
            if resource.resource_type == "AWS::S3::Bucket":
                s3_bucket_name = resource.physical_resource_id

        if not s3_bucket_name:
            raise ManagedStackError("Managed stack does not have S3 bucket")

        s3 = boto3.resource("s3", region_name=region)
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
