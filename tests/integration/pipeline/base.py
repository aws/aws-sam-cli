import os
import shutil
import logging
import uuid
from pathlib import Path
from typing import List, Optional, Set, Tuple, Any
from unittest import TestCase
from unittest.mock import Mock

import boto3
import botocore.exceptions
from botocore.exceptions import ClientError

from samcli.lib.pipeline.bootstrap.stage import Stage


class PipelineBase(TestCase):
    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command


class InitIntegBase(PipelineBase):
    generated_files: List[Path] = []

    @classmethod
    def setUpClass(cls) -> None:
        # we need to compare the whole generated template, which is
        # larger than normal diff size limit
        cls.maxDiff = None

    def setUp(self) -> None:
        super().setUp()
        self.generated_files = []

    def tearDown(self) -> None:
        for generated_file in self.generated_files:
            if generated_file.is_dir():
                shutil.rmtree(generated_file, ignore_errors=True)
            elif generated_file.exists():
                generated_file.unlink()
        super().tearDown()

    def get_init_command_list(self, with_bootstrap=False):
        command_list = [self.base_command(), "pipeline", "init"]
        if with_bootstrap:
            command_list.append("--bootstrap")
        return command_list


class BootstrapIntegBase(PipelineBase):
    region = "us-east-1"
    stack_names: List[str]
    cf_client: Any
    randomized_stage_suffix: str

    @classmethod
    def setUpClass(cls):
        cls.cf_client = boto3.client("cloudformation", region_name=cls.region)
        cls.randomized_stage_suffix = uuid.uuid4().hex[-6:]

    def setUp(self):
        self.stack_names = []
        super().setUp()
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "pipeline"), ignore_errors=True)

    def tearDown(self):
        for stack_name in self.stack_names:
            self._cleanup_s3_buckets(stack_name)
            self.cf_client.delete_stack(StackName=stack_name)
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "pipeline"), ignore_errors=True)
        super().tearDown()

    def _cleanup_s3_buckets(self, stack_name):
        try:
            stack_resources = self.cf_client.describe_stack_resources(StackName=stack_name)
            buckets = [
                resource
                for resource in stack_resources["StackResources"]
                if resource["ResourceType"] == "AWS::S3::Bucket"
            ]
            session = boto3.session.Session()
            s3_client = session.resource("s3")
            for bucket in buckets:
                bucket = s3_client.Bucket(bucket.get("PhysicalResourceId"))
                bucket.object_versions.delete()
                bucket.delete()
        except botocore.exceptions.ClientError:
            """No need to fail in cleanup"""

    def get_bootstrap_command_list(
        self,
        no_interactive: bool = False,
        stage_configuration_name: Optional[str] = None,
        profile_name: Optional[str] = None,
        region: Optional[str] = None,
        pipeline_user: Optional[str] = None,
        pipeline_execution_role: Optional[str] = None,
        cloudformation_execution_role: Optional[str] = None,
        bucket: Optional[str] = None,
        create_image_repository: bool = False,
        image_repository: Optional[str] = None,
        no_confirm_changeset: bool = False,
    ):
        command_list = [self.base_command(), "pipeline", "bootstrap"]

        if no_interactive:
            command_list += ["--no-interactive"]
        if stage_configuration_name:
            command_list += ["--stage", stage_configuration_name]
        if profile_name:
            command_list += ["--profile", profile_name]
        if region:
            command_list += ["--region", region]
        if pipeline_user:
            command_list += ["--pipeline-user", pipeline_user]
        if pipeline_execution_role:
            command_list += ["--pipeline-execution-role", pipeline_execution_role]
        if cloudformation_execution_role:
            command_list += ["--cloudformation-execution-role", cloudformation_execution_role]
        if bucket:
            command_list += ["--bucket", bucket]
        if create_image_repository:
            command_list += ["--create-image-repository"]
        if image_repository:
            command_list += ["--image-repository", image_repository]
        if no_confirm_changeset:
            command_list += ["--no-confirm-changeset"]

        return command_list

    def _extract_created_resource_logical_ids(self, stack_name: str) -> List[str]:
        response = self.cf_client.describe_stack_resources(StackName=stack_name)
        return [resource["LogicalResourceId"] for resource in response["StackResources"]]

    def _stack_exists(self, stack_name) -> bool:
        try:
            self.cf_client.describe_stacks(StackName=stack_name)
            return True
        except ClientError as ex:
            if "does not exist" in ex.response.get("Error", {}).get("Message", ""):
                return False
            raise ex

    def _get_stage_and_stack_name(self, suffix: str = "") -> Tuple[str, str]:
        # Method expects method name which can be a full path. Eg: test.integration.test_bootstrap_command.method_name
        method_name = self.id().split(".")[-1]
        stage_configuration_name = method_name.replace("_", "-") + suffix + "-" + self.randomized_stage_suffix

        mock_env = Mock()
        mock_env.name = stage_configuration_name
        stack_name = Stage._get_stack_name(mock_env)

        return stage_configuration_name, stack_name
