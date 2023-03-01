from pathlib import Path

import boto3
import os

from tempfile import TemporaryDirectory

from typing import List

from samcli.lib.bootstrap.bootstrap import SAM_CLI_STACK_NAME
from tests.end_to_end.test_stages import (
    EndToEndBaseStage,
    DefaultBuildStage,
    DefaultInitStage,
    DefaultDeployStage,
    DefaultRemoteInvokeStage,
    DefaultDeleteStage,
)
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.integration.delete.delete_integ_base import DeleteIntegBase
from tests.integration.init.test_init_base import InitIntegBase
from tests.integration.list.stack_outputs.stack_outputs_integ_base import StackOutputsIntegBase


class EndToEndBase(InitIntegBase, BuildIntegBase, StackOutputsIntegBase, DeleteIntegBase):
    runtime = ""
    dependency_manager = ""
    app_template = ""
    app_name = "sam-app"

    @classmethod
    def setUpClass(cls):
        InitIntegBase.setUpClass()
        BuildIntegBase.setUpClass()
        StackOutputsIntegBase.setUpClass()
        DeleteIntegBase.setUpClass()

    def setUp(self):
        super().setUp()
        self.stacks = []
        self.cfn_client = boto3.client("cloudformation")

    def tearDown(self):
        self.delete_stacks()
        super().tearDown()

    def delete_stacks(self):
        for stack in self.stacks:
            # because of the termination protection, do not delete aws-sam-cli-managed-default stack
            stack_name = stack["name"]
            if stack_name != SAM_CLI_STACK_NAME:
                try:
                    self.cfn_client.delete_stack(StackName=stack_name)
                except Exception:
                    pass

    @staticmethod
    def run_tests(stages: List[EndToEndBaseStage]):
        for stage in stages:
            command_result = stage.run_stage()
            stage.validate(command_result)

    def default_workflow(self):
        with TemporaryDirectory() as temp:
            os.chdir(temp)
            self.template_path = str(Path(temp) / self.app_name / "template.yaml")
            stack_name = self._method_to_stack_name(self.id())
            init_command_list = self.get_init_command(temp)
            build_command_list = self.get_command_list()
            deploy_command_list = self.get_deploy_command(stack_name)
            stages = [
                DefaultInitStage(init_command_list, app_name=self.app_name),
                DefaultBuildStage(build_command_list),
                DefaultDeployStage(deploy_command_list),
                DefaultRemoteInvokeStage(command_list=[]),
                DefaultDeleteStage(command_list=[]),
            ]
            self.run_tests(stages)

    def get_init_command(self, temp_directory):
        return self.get_command(
            runtime=self.runtime,
            dependency_manager=self.dependency_manager,
            architecture="x86_64",
            app_template=self.app_template,
            name=self.app_name,
            no_interactive=True,
            output=temp_directory,
        )

    def get_deploy_command(self, stack_name):
        self.stacks.append({"name": stack_name})
        return self.get_deploy_command_list(
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            confirm_changeset=False,
            force_upload=True,
            s3_bucket=self.s3_bucket.name,
        )
