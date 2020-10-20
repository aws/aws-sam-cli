import os
import tempfile
import uuid
import time
from subprocess import Popen, PIPE, TimeoutExpired
from unittest import skipIf

import boto3
from parameterized import parameterized

from tests.regression.deploy.regression_deploy_base import DeployRegressionBase
from tests.regression.package.regression_package_base import PackageRegressionBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Package Regression tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master and tests are not run by Canary.
SKIP_DEPLOY_REGRESSION_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
TIMEOUT = 300
# Only testing return codes to be equivalent


@skipIf(SKIP_DEPLOY_REGRESSION_TESTS, "Skip deploy regression tests in CI/CD only")
class TestDeployRegression(PackageRegressionBase, DeployRegressionBase):
    def setUp(self):
        self.sns_arn = os.environ.get("AWS_SNS")
        self.kms_key = os.environ.get("AWS_KMS_KEY")
        self.stack_names = []
        self.cf_client = boto3.client("cloudformation")
        time.sleep(CFN_SLEEP)
        super().setUp()

    def tearDown(self):
        for stack_name in self.stack_names:
            self.cf_client.delete_stack(StackName=stack_name)
        super().tearDown()

    def prepare_package(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        output_template_file = tempfile.NamedTemporaryFile(delete=False)
        package_command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, template_file=template_path, output_template_file=output_template_file.name
        )

        package_process = Popen(package_command_list, stdout=PIPE)
        try:
            stdout, _ = package_process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            package_process.kill()
            raise
        self.assertEqual(package_process.returncode, 0)
        return output_template_file.name

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_all_args(self, template_file):

        output_template_file = self.prepare_package(template_file=template_file)

        sam_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(sam_stack_name)

        aws_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(aws_stack_name)

        arguments = {
            "template_file": output_template_file,
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

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_no_stack_name(self, template_file):
        output_template_file = self.prepare_package(template_file=template_file)

        arguments = {
            "template_file": output_template_file,
            "capabilities": "CAPABILITY_IAM",
            "s3_prefix": "regress_deploy",
            "force_upload": True,
            "notification_arns": self.sns_arn,
            "parameter_overrides": "Parameter=Clarity",
            "kms_key_id": self.kms_key,
            "tags": "integ=true clarity=yes",
        }

        self.deploy_regression_check(arguments, sam_return_code=2, aws_return_code=2)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_no_capabilities(self, template_file):
        output_template_file = self.prepare_package(template_file=template_file)

        sam_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(sam_stack_name)

        aws_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(aws_stack_name)

        arguments = {
            "template_file": output_template_file,
            "aws_stack_name": aws_stack_name,
            "sam_stack_name": sam_stack_name,
            "s3_prefix": "regress_deploy",
            "force_upload": True,
            "notification_arns": self.sns_arn,
            "parameter_overrides": "Parameter=Clarity",
            "kms_key_id": self.kms_key,
            "tags": "integ=true clarity=yes",
        }

        self.deploy_regression_check(arguments, sam_return_code=1, aws_return_code=255)

    def test_deploy_with_no_template_file(self):
        sam_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(sam_stack_name)

        aws_stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(aws_stack_name)

        arguments = {
            "aws_stack_name": aws_stack_name,
            "sam_stack_name": sam_stack_name,
            "s3_prefix": "regress_deploy",
            "force_upload": True,
            "notification_arns": self.sns_arn,
            "parameter_overrides": "Parameter=Clarity",
            "kms_key_id": self.kms_key,
            "tags": "integ=true clarity=yes",
        }
        # if no template file is specified, sam cli looks for a template.yaml in the current working directory.
        self.deploy_regression_check(arguments, sam_return_code=1, aws_return_code=2)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_no_changes(self, template_file):
        output_template_file = self.prepare_package(template_file=template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

        arguments = {
            "template_file": output_template_file,
            "capabilities": "CAPABILITY_IAM",
            "sam_stack_name": stack_name,
            "aws_stack_name": stack_name,
            "s3_prefix": "regress_deploy",
            "force_upload": True,
            "notification_arns": self.sns_arn,
            "parameter_overrides": "Parameter=Clarity",
            "kms_key_id": self.kms_key,
            "tags": "integ=true clarity=yes",
        }

        self.deploy_regression_check(arguments, sam_return_code=0, aws_return_code=0)
