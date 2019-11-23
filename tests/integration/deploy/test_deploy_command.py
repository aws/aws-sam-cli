import os
import tempfile
import uuid
import time
from subprocess import Popen, PIPE
from unittest import skipIf

import boto3
from parameterized import parameterized

from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI

# Deploy tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD and when the branch is not master.
SKIP_DEPLOY_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI
CFN_SLEEP = 3


@skipIf(SKIP_DEPLOY_TESTS, "Skip deploy tests in CI/CD only")
class TestDeploy(PackageIntegBase, DeployIntegBase):
    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        self.sns_arn = os.environ.get("AWS_SNS")
        self.stack_names = []
        time.sleep(CFN_SLEEP)
        super(TestDeploy, self).setUp()

    def tearDown(self):
        for stack_name in self.stack_names:
            self.cf_client.delete_stack(StackName=stack_name)
        super(TestDeploy, self).tearDown()

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_package_and_deploy_no_s3_bucket_all_args(self, template_file):
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
                force_upload=True,
                notification_arns=self.sns_arn,
                parameter_overrides="Parameter=Clarity",
                kms_key_id=self.kms_key,
                tags="integ=true clarity=yes",
            )

            deploy_process = Popen(deploy_command_list_execute, stdout=PIPE)
            deploy_process.wait()
            self.assertEqual(deploy_process.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_no_package_and_deploy_with_s3_bucket_all_args(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE)
        deploy_process_execute.wait()
        self.assertEqual(deploy_process_execute.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_no_package_and_deploy_with_s3_bucket_all_args_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=True,
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        deploy_process_execute.communicate("Y".encode())
        self.assertEqual(deploy_process_execute.returncode, 0)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_s3_bucket(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE)
        deploy_process_execute.wait()
        # Error asking for s3 bucket
        self.assertEqual(deploy_process_execute.returncode, 1)
        stderr = b"".join(deploy_process_execute.stderr.readlines()).strip()
        self.assertIn(
            bytes(
                f"S3 Bucket not specified, use --s3-bucket to specify a bucket name or run sam deploy --guided",
                encoding="utf-8",
            ),
            stderr,
        )

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_stack_name(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE)
        deploy_process_execute.wait()
        # Error no stack name present
        self.assertEqual(deploy_process_execute.returncode, 2)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_capabilities(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE)
        deploy_process_execute.wait()
        # Error capabilities not specified
        self.assertEqual(deploy_process_execute.returncode, 1)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_without_template_file(self, template_file):
        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            stack_name=stack_name,
            s3_prefix="integ_deploy",
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE)
        deploy_process_execute.wait()
        # Error template file not specified
        self.assertEqual(deploy_process_execute.returncode, 1)

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_with_s3_bucket_switch_region(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.bucket_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE)
        deploy_process_execute.wait()
        # Deploy should succeed
        self.assertEqual(deploy_process_execute.returncode, 0)

        # Try to deploy to another region.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_prefix="integ_deploy",
            s3_bucket=self.bucket_name,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes",
            confirm_changeset=False,
            region="eu-west-2",
        )

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE)
        deploy_process_execute.wait()
        # Deploy should fail, asking for s3 bucket
        self.assertEqual(deploy_process_execute.returncode, 1)
        stderr = b"".join(deploy_process_execute.stderr.readlines()).strip()
        self.assertIn(
            bytes(
                f"Error: Failed to create/update stack {stack_name} : "
                f"deployment s3 bucket is in a different region, try sam deploy --guided",
                encoding="utf-8",
            ),
            stderr,
        )

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        deploy_process_execute.communicate("{}\n\n\n\n\n\n".format(stack_name).encode())

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_parameter(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        deploy_process_execute.communicate("{}\n\nSuppliedParameter\n\n\n\n".format(stack_name).encode())

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_capabilities(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        deploy_process_execute.communicate(
            "{}\n\nSuppliedParameter\n\nn\nCAPABILITY_IAM CAPABILITY_NAMED_IAM\n\n".format(stack_name).encode()
        )

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))

    @parameterized.expand(["aws-serverless-function.yaml"])
    def test_deploy_guided_set_confirm_changeset(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = "a" + str(uuid.uuid4()).replace("-", "")[:10]
        self.stack_names.append(stack_name)

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = Popen(deploy_command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        deploy_process_execute.communicate("{}\n\nSuppliedParameter\nY\n\n\nY\n".format(stack_name).encode())

        # Deploy should succeed with a managed stack
        self.assertEqual(deploy_process_execute.returncode, 0)
        self.stack_names.append(SAM_CLI_STACK_NAME)
        # Remove samconfig.toml
        os.remove(self.test_data_path.joinpath(DEFAULT_CONFIG_FILE_NAME))
