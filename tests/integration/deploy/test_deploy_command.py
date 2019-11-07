import os
import tempfile
import uuid
from subprocess import Popen, PIPE
from unittest import skipIf

import boto3
from parameterized import parameterized

from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD and when the branch is not master.
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI


@skipIf(SKIP_DEPLOY_TESTS, "Skip deploy tests in CI/CD only")
class TestDeploy(PackageIntegBase, DeployIntegBase):
    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        self.sns_arn = os.environ.get("AWS_SNS")
        self.stack_names = []
        super(TestDeploy, self).setUp()

    def tearDown(self):
        for stack_name in self.stack_names:
            self.cf_client.delete_stack(StackName=stack_name)
        super(TestDeploy, self).tearDown()

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_all_args(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        with tempfile.NamedTemporaryFile(delete=False) as output_template_file:
            # Package necessary artifacts.
            package_command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name, template=template_path, output_template_file=output_template_file.name
            )

            package_process = Popen(package_command_list, stdout=PIPE)
            package_process.wait()

            self.assertEqual(package_process.returncode, 0)

            stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
            self.stack_names.append(stack_name)

            # Deploy and only show changeset.
            deploy_command_list_no_execute = self.get_deploy_command_list(
                template_file=output_template_file.name,
                stack_name=stack_name,
                capabilities="CAPABILITY_IAM",
                s3_prefix="integ_deploy",
                s3_bucket=self.s3_bucket.name,
                force_upload=True,
                notification_arns=self.sns_arn,
                parameter_overrides="Parameter=Clarity",
                kms_key_id=self.kms_key,
                no_execute_changeset=True,
                tags="integ=true clarity=yes",
            )

            deploy_process_no_execute = Popen(deploy_command_list_no_execute, stdout=PIPE)
            deploy_process_no_execute.wait()
            self.assertEqual(deploy_process_no_execute.returncode, 0)

            # Deploy the given stack with the changeset.
            deploy_command_list_execute = self.get_deploy_command_list(
                template_file=output_template_file.name,
                stack_name=stack_name,
                capabilities="CAPABILITY_IAM",
                s3_prefix="integ_deploy",
                s3_bucket=self.s3_bucket.name,
                force_upload=True,
                notification_arns=self.sns_arn,
                parameter_overrides="Parameter=Clarity",
                kms_key_id=self.kms_key,
                tags="integ=true clarity=yes",
            )

            deploy_process = Popen(deploy_command_list_execute, stdout=PIPE)
            deploy_process.wait()
            self.assertEqual(deploy_process.returncode, 0)
