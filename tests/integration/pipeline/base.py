import os
import shutil
from pathlib import Path
from typing import List, Optional, Set, Tuple, Any
from unittest import TestCase
from unittest.mock import Mock

import boto3
from botocore.exceptions import ClientError

from samcli.lib.pipeline.bootstrap.environment import Environment


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

    def get_init_command_list(
        self,
    ):
        command_list = [self.base_command(), "pipeline", "init"]
        return command_list


class BootstrapIntegBase(PipelineBase):
    stack_names: List[str]
    cf_client: Any

    @classmethod
    def setUpClass(cls):
        cls.cf_client = boto3.client("cloudformation")

    def setUp(self):
        self.stack_names = []
        super().setUp()

    def tearDown(self):
        for stack_name in self.stack_names:
            self.cf_client.delete_stack(StackName=stack_name)
        shutil.rmtree(os.path.join(os.getcwd(), ".aws-sam", "pipeline"), ignore_errors=True)
        super().tearDown()

    def get_bootstrap_command_list(
        self,
        no_interactive: bool = False,
        env_name: Optional[str] = None,
        pipeline_user: Optional[str] = None,
        pipeline_execution_role: Optional[str] = None,
        cloudformation_execution_role: Optional[str] = None,
        artifacts_bucket: Optional[str] = None,
        create_image_repository: bool = False,
        image_repository: Optional[str] = None,
        no_confirm_changeset: bool = False,
    ):
        command_list = [self.base_command(), "pipeline", "bootstrap"]

        if no_interactive:
            command_list += ["--no-interactive"]
        if env_name:
            command_list += ["--environment", env_name]
        if pipeline_user:
            command_list += ["--pipeline-user", pipeline_user]
        if pipeline_execution_role:
            command_list += ["--pipeline-execution-role", pipeline_execution_role]
        if cloudformation_execution_role:
            command_list += ["--cloudformation-execution-role", cloudformation_execution_role]
        if artifacts_bucket:
            command_list += ["--artifacts-bucket", artifacts_bucket]
        if create_image_repository:
            command_list += ["--create-image-repository"]
        if image_repository:
            command_list += ["--image-repository", image_repository]
        if no_confirm_changeset:
            command_list += ["--no-confirm-changeset"]

        return command_list

    def _extract_created_resource_logical_ids(self, stack_name: str) -> Set[str]:
        response = self.cf_client.describe_stack_resources(StackName=stack_name)
        return {resource["LogicalResourceId"] for resource in response["StackResources"]}

    def _stack_exists(self, stack_name) -> bool:
        try:
            self.cf_client.describe_stacks(StackName=stack_name)
            return True
        except ClientError as ex:
            if "does not exist" in ex.response.get("Error", {}).get("Message", ""):
                return False
            raise ex

    def _get_env_and_stack_name(self, suffix: str = "") -> Tuple[str, str]:
        # Method expects method name which can be a full path. Eg: test.integration.test_bootstrap_command.method_name
        method_name = self.id().split(".")[-1]
        env_name = method_name.replace("_", "-") + suffix

        mock_env = Mock()
        mock_env.name = env_name
        stack_name = Environment._get_stack_name(mock_env)

        return env_name, stack_name
