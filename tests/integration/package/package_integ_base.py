import os
import uuid
import json
import time
from pathlib import Path
from unittest import TestCase

import boto3
from botocore.exceptions import ClientError

from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack

CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")
SLEEP = 3


class PackageIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION")
        """
        Our integration tests use S3 bucket and ECR Repo to run several tests.
        Given that S3 objects are eventually consistent and we are using same bucket for
        lot of integration tests, we want to have multiple buckets to reduce
        transient failures. In order to achieve this we created 3 buckets one for each python version we support (3.6,
        3.7 and 3.8). Tests running for respective python version will use respective bucket.

        AWS_S3 will point to a new environment variable AWS_S3_36 or AWS_S3_37 or AWS_S3_38. This is controlled by
        Appveyor. These environment variables will hold bucket name to run integration tests. Eg:

        For Python36:
        AWS_S3=AWS_S3_36
        AWS_S3_36=aws-sam-cli-canary-region-awssamclitestbucket-forpython36

        AWS_ECR will point to a new environment variable AWS_ECR_36 or AWS_ECR_37 or AWS_ECR_38. This is controlled by
        Appveyor. These environment variables will hold bucket name to run integration tests. Eg:

        For Python36:
        AWS_S3=AWS_ECR_36
        AWS_S3_36=123456789012.dkr.ecr.us-east-1.amazonaws.com/sam-cli-py36

        For backwards compatibility we are falling back to reading AWS_S3 so that current tests keep working.
        For backwards compatibility we are falling back to reading AWS_ECR so that current tests keep working.
        """
        s3_bucket_from_env_var = os.environ.get("AWS_S3")
        ecr_repo_from_env_var = os.environ.get("AWS_ECR")
        if s3_bucket_from_env_var:
            cls.pre_created_bucket = os.environ.get(s3_bucket_from_env_var, False)
        else:
            cls.pre_created_bucket = False
        if ecr_repo_from_env_var:
            cls.pre_created_ecr_repo = os.environ.get(ecr_repo_from_env_var, False)
        else:
            cls.pre_created_ecr_repo = False
        cls.ecr_repo_name = (
            cls.pre_created_ecr_repo if cls.pre_created_ecr_repo else str(uuid.uuid4()).replace("-", "")[:10]
        )
        cls.bucket_name = cls.pre_created_bucket if cls.pre_created_bucket else str(uuid.uuid4())
        cls.test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "package")

        # Intialize S3 client
        s3 = boto3.resource("s3")
        cls.ecr = boto3.client("ecr")
        # Use a pre-created KMS Key
        cls.kms_key = os.environ.get("AWS_KMS_KEY")
        # Use a pre-created S3 Bucket if present else create a new one
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        if not cls.pre_created_bucket:
            cls.s3_bucket.create()
            time.sleep(SLEEP)
            bucket_versioning = s3.BucketVersioning(cls.bucket_name)
            bucket_versioning.enable()
            time.sleep(SLEEP)
        if not cls.pre_created_ecr_repo:
            ecr_result = cls.ecr.create_repository(repositoryName=cls.ecr_repo_name)
            cls.ecr_repo_name = ecr_result.get("repository", {}).get("repositoryUri", None)
            time.sleep(SLEEP)

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(
        self,
        s3_bucket=None,
        template=None,
        template_file=None,
        s3_prefix=None,
        output_template_file=None,
        use_json=False,
        force_upload=False,
        no_progressbar=False,
        kms_key_id=None,
        metadata=None,
        image_repository=None,
        image_repositories=None,
        resolve_s3=False,
    ):
        command_list = [self.base_command(), "package"]

        if s3_bucket:
            command_list = command_list + ["--s3-bucket", str(s3_bucket)]
        if template:
            command_list = command_list + ["--template", str(template)]
        if template_file:
            command_list = command_list + ["--template-file", str(template_file)]

        if s3_prefix:
            command_list = command_list + ["--s3-prefix", str(s3_prefix)]

        if output_template_file:
            command_list = command_list + ["--output-template-file", str(output_template_file)]
        if kms_key_id:
            command_list = command_list + ["--kms-key-id", str(kms_key_id)]
        if use_json:
            command_list = command_list + ["--use-json"]
        if force_upload:
            command_list = command_list + ["--force-upload"]
        if no_progressbar:
            command_list = command_list + ["--no-progressbar"]
        if metadata:
            command_list = command_list + ["--metadata", json.dumps(metadata)]
        if image_repository:
            command_list = command_list + ["--image-repository", str(image_repository)]
        if image_repositories:
            command_list = command_list + ["--image-repositories", str(image_repositories)]
        if resolve_s3:
            command_list = command_list + ["--resolve-s3"]
        return command_list

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
