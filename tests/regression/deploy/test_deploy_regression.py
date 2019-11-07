import os
import tempfile
import uuid
from subprocess import Popen, PIPE
from unittest import skipIf

import boto3
from parameterized import parameterized

from tests.regression.deploy.regression_deploy_base import DeployRegressionBase
from tests.regression.package.regression_package_base import PackageRegressionBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI

# Package Regression tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD and when the branch is not master.
SKIP_DEPLOY_REGRESSION_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI

# Only testing return codes to be equivalent


@skipIf(SKIP_DEPLOY_REGRESSION_TESTS, "Skip deploy regression tests in CI/CD only")
class TestDeployRegression(PackageRegressionBase, DeployRegressionBase):
    def setUp(self):
        self.sns_arn = os.environ.get("AWS_SNS")
        self.kms_key = os.environ.get("AWS_KMS_KEY")
        self.stack_names = []
        self.cf_client = boto3.client("cloudformation")
        super(TestDeployRegression, self).setUp()

    def tearDown(self):
        for stack_name in self.stack_names:
            self.cf_client.delete_stack(StackName=stack_name)
        super(TestDeployRegression, self).tearDown()

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_all_args(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        with tempfile.NamedTemporaryFile(delete=False) as output_template_file:
            # Package necessary artifacts.
            package_command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name,
                template_file=template_path,
                output_template_file=output_template_file.name,
            )

            package_process = Popen(package_command_list, stdout=PIPE)
            package_process.wait()
            self.assertEqual(package_process.returncode, 0)

            sam_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
            self.stack_names.append(sam_stack_name)

            aws_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
            self.stack_names.append(aws_stack_name)

            arguments = {
                "template_file": output_template_file.name,
                "aws_stack_name": aws_stack_name,
                "sam_stack_name": sam_stack_name,
                "capabilities": "CAPABILITY_IAM",
                "s3_prefix": "regress_deploy",
                "force_upload": True,
                "notification_arns": self.sns_arn,
                "parameter_overrides": "Parameter=Clarity",
                "kms_key_id": self.kms_key,
                "tags": "integ=true clarity=yes",
            }

            self.deploy_regression_check(arguments)
