import os
import time
from unittest import skipIf

import boto3
import docker
import pytest
from botocore.exceptions import ClientError
from parameterized import parameterized

from tests.integration.delete.delete_integ_base import DeleteIntegBase
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

# Delete tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master or tests are not run by Canary
SKIP_DELETE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_DELETE_TESTS, "Skip delete tests in CI/CD only")
class TestDelete(DeleteIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.docker_client = docker.from_env()
        cls.local_images = [
            ("alpine", "latest"),
        ]
        # setup some images locally by pulling them.
        for repo, tag in cls.local_images:
            cls.docker_client.api.pull(repository=repo, tag=tag)
        super().setUpClass()

    def setUp(self):
        # Save reference to session object to get region_name
        self._session = boto3.session.Session()
        self.cf_client = self._session.client("cloudformation")
        self.s3_client = self._session.client("s3")
        self.sns_arn = os.environ.get("AWS_SNS")
        time.sleep(CFN_SLEEP)
        super().setUp()

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_s3_options(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            image_repository=self.ecr_repo_name,
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region=self._session.region_name,
        )
        deploy_process_execute = run_command(deploy_command_list)

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name,
            region=self._session.region_name,
            no_prompts=True,
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
        )
        delete_process_execute = run_command(delete_command_list)

        self.assertEqual(delete_process_execute.process.returncode, 0)

        # Check if the stack was deleted
        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

        # Check for zero objects in bucket
        s3_objects_resp = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=self.s3_prefix)
        self.assertEqual(s3_objects_resp["KeyCount"], 0)

    @pytest.mark.flaky(reruns=3)
    def test_delete_command_no_stack_deployed(self):

        stack_name = self._method_to_stack_name(self.id())

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, region=self._session.region_name, no_prompts=True
        )

        delete_process_execute = run_command(delete_command_list)
        self.assertEqual(delete_process_execute.process.returncode, 0)
        self.assertIn(
            f"Error: The input stack {stack_name} does not exist on Cloudformation", str(delete_process_execute.stdout)
        )

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_no_prompts_with_s3_prefix_present_zip(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        config_file_name = stack_name + ".toml"
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, guided=True, config_file=config_file_name
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        config_file_path = self.test_data_path.joinpath(config_file_name)
        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, config_file=config_file_path, region=self._session.region_name, no_prompts=True
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

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_no_prompts_with_s3_prefix_present_image(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        config_file_name = stack_name + ".toml"
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, guided=True, config_file=config_file_name, image_repository=self.ecr_repo_name
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list, f"{stack_name}\n\n{self.ecr_repo_name}\n\n\ny\n\n\n\n\n\n".encode()
        )

        config_file_path = self.test_data_path.joinpath(config_file_name)
        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, config_file=config_file_path, region=self._session.region_name, no_prompts=True
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

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_guided_config_file_present(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        config_file_name = stack_name + ".toml"
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path, guided=True, config_file=config_file_name
        )

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\n\n\n\n\n".format(stack_name).encode()
        )

        config_file_path = self.test_data_path.joinpath(config_file_name)
        delete_command_list = self.get_delete_command_list(stack_name=stack_name, config_file=config_file_path)

        delete_process_execute = run_command_with_input(delete_command_list, "y\nn\ny\n".encode())

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

        # Remove the local config file created
        if os.path.isfile(config_file_path):
            os.remove(config_file_path)

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_no_config_file_zip(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        deploy_command_list = self.get_deploy_command_list(template_file=template_path, guided=True)

        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n\n\n\n\nn\n\n\n".format(stack_name).encode()
        )

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, region=self._session.region_name, no_prompts=True
        )

        delete_process_execute = run_command(delete_command_list)
        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_no_prompts_no_s3_prefix_zip(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region=self._session.region_name,
        )

        deploy_process_execute = run_command(deploy_command_list)

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, region=self._session.region_name, no_prompts=True
        )

        delete_process_execute = run_command(delete_command_list)

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_no_prompts_no_s3_prefix_image(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        # Try to deploy to another region.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            image_repository=self.ecr_repo_name,
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region=self._session.region_name,
        )

        deploy_process_execute = run_command(deploy_command_list)

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, region=self._session.region_name, no_prompts=True
        )

        delete_process_execute = run_command(delete_command_list)

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @parameterized.expand(
        [os.path.join("deep-nested", "template.yaml"), os.path.join("deep-nested-image", "template.yaml")]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_nested_stacks(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        # Package and Deploy in one go without confirming change set.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            # Note(xinhol): --capabilities does not allow passing multiple, we need to fix it
            # here we use samconfig-deep-nested.toml as a workaround
            config_file=self.test_data_path.joinpath("samconfig-deep-nested.toml"),
            s3_prefix=self.s3_prefix,
            s3_bucket=self.s3_bucket.name,
            force_upload=True,
            notification_arns=self.sns_arn,
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            image_repository=self.ecr_repo_name,
        )

        deploy_process_execute = run_command(deploy_command_list)

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, region=self._session.region_name, no_prompts=True
        )

        delete_process_execute = run_command(delete_command_list)

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @pytest.mark.flaky(reruns=3)
    def test_delete_stack_termination_protection_enabled(self):
        template_str = """
        AWSTemplateFormatVersion: '2010-09-09'
        Description: Stack for testing termination protection enabled stacks.
        Resources:
          MyRepository:
            Type: AWS::ECR::Repository
            Properties:
                RepositoryName: "test-termination-protection-repository"
        """

        stack_name = self._method_to_stack_name(self.id())

        self.cf_client.create_stack(StackName=stack_name, TemplateBody=template_str, EnableTerminationProtection=True)

        delete_command_list = self.get_delete_command_list(
            stack_name=stack_name, region=self._session.region_name, no_prompts=True
        )

        delete_process_execute = run_command(delete_command_list)

        self.assertEqual(delete_process_execute.process.returncode, 1)
        self.assertIn(
            bytes(
                "TerminationProtection is enabled",
                encoding="utf-8",
            ),
            delete_process_execute.stderr,
        )

        self.cf_client.update_termination_protection(StackName=stack_name, EnableTerminationProtection=False)

        delete_process_execute = run_command(delete_command_list)
        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @pytest.mark.flaky(reruns=3)
    def test_no_prompts_no_stack_name(self):

        delete_command_list = self.get_delete_command_list(no_prompts=True)
        delete_process_execute = run_command(delete_command_list)
        self.assertEqual(delete_process_execute.process.returncode, 2)

    @pytest.mark.flaky(reruns=3)
    def test_no_prompts_no_region(self):
        stack_name = self._method_to_stack_name(self.id())

        delete_command_list = self.get_delete_command_list(stack_name=stack_name, no_prompts=True)
        delete_process_execute = run_command(delete_command_list)
        self.assertEqual(delete_process_execute.process.returncode, 2)

    @parameterized.expand(
        [
            "aws-serverless-function.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_guided_no_stack_name_no_region(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region=self._session.region_name,
        )
        deploy_process_execute = run_command(deploy_command_list)

        delete_command_list = self.get_delete_command_list()
        delete_process_execute = run_command_with_input(delete_command_list, "{}\ny\ny\n".format(stack_name).encode())

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @parameterized.expand(
        [
            "aws-ecr-repository.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_guided_ecr_repository_present(self, template_file):
        template_path = self.delete_test_data_path.joinpath(template_file)
        stack_name = self._method_to_stack_name(self.id())

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region=self._session.region_name,
        )
        deploy_process_execute = run_command(deploy_command_list)

        delete_command_list = self.get_delete_command_list(stack_name=stack_name, region=self._session.region_name)
        delete_process_execute = run_command_with_input(delete_command_list, "y\ny\ny\n".encode())

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @parameterized.expand(
        [
            "aws-serverless-function-image.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_guided_no_s3_prefix_image(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        # Try to deploy to another region.
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            image_repository=self.ecr_repo_name,
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region=self._session.region_name,
        )

        deploy_process_execute = run_command(deploy_command_list)

        delete_command_list = self.get_delete_command_list(stack_name=stack_name, region=self._session.region_name)

        delete_process_execute = run_command_with_input(delete_command_list, "y\n".encode())

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

    @parameterized.expand(
        [
            "aws-serverless-function-retain.yaml",
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_delete_guided_retain_s3_artifact(self, template_file):
        template_path = self.delete_test_data_path.joinpath(template_file)
        stack_name = self._method_to_stack_name(self.id())

        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            s3_bucket=self.bucket_name,
            s3_prefix=self.s3_prefix,
            force_upload=True,
            notification_arns=self.sns_arn,
            parameter_overrides="Parameter=Clarity",
            kms_key_id=self.kms_key,
            no_execute_changeset=False,
            tags="integ=true clarity=yes foo_bar=baz",
            confirm_changeset=False,
            region=self._session.region_name,
        )
        deploy_process_execute = run_command(deploy_command_list)
        self.add_left_over_resources_from_stack(stack_name)

        delete_command_list = self.get_delete_command_list(stack_name=stack_name, region=self._session.region_name)
        delete_process_execute = run_command_with_input(delete_command_list, "y\nn\nn\n".encode())

        self.assertEqual(delete_process_execute.process.returncode, 0)

        try:
            resp = self.cf_client.describe_stacks(StackName=stack_name)
        except ClientError as ex:
            self.assertIn(f"Stack with id {stack_name} does not exist", str(ex))

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
