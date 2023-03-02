from pathlib import Path

import os

from tempfile import TemporaryDirectory

from typing import List

from tests.end_to_end.test_stages import (
    EndToEndBaseStage,
    DefaultBuildStage,
    DefaultInitStage,
    DefaultDeployStage,
    DefaultRemoteInvokeStage,
    DefaultDeleteStage,
    DefaultStackOutputsStage,
    DefaultSyncStage,
)
from tests.integration.delete.delete_integ_base import DeleteIntegBase
from tests.integration.init.test_init_base import InitIntegBase
from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.integration.list.stack_outputs.stack_outputs_integ_base import StackOutputsIntegBase


class EndToEndBase(InitIntegBase, StackOutputsIntegBase, DeleteIntegBase, SyncIntegBase):
    dependency_layer = True
    app_name = "sam-app"
    runtime = ""
    dependency_manager = ""
    app_template = ""

    def setUp(self):
        super().setUp()
        self.stacks = []

    def default_workflow(self):
        stack_name = self._method_to_stack_name(self.id())
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_dir)
            build_command_list = self.get_command_list()
            deploy_command_list = self._get_deploy_command(stack_name)
            delete_command_list = self._get_delete_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            stages = [
                DefaultInitStage(init_command_list, self.app_name),
                DefaultBuildStage(build_command_list),
                DefaultDeployStage(deploy_command_list),
                DefaultRemoteInvokeStage(stack_name),
                DefaultStackOutputsStage(stack_outputs_command_list),
                DefaultDeleteStage(delete_command_list, stack_name),
            ]
            self._run_tests(stages)

    def default_sync_workflow(self):
        stack_name = self._method_to_stack_name(self.id())
        with EndToEndTestContext(self.app_name) as e2e_context:
            self.template_path = e2e_context.template_path
            init_command_list = self._get_init_command(e2e_context.working_dir)
            sync_command_list = self._get_sync_command(stack_name)
            delete_command_list = self._get_delete_command(stack_name)
            stack_outputs_command_list = self._get_stack_outputs_command(stack_name)
            stages = [
                DefaultInitStage(init_command_list, self.app_name),
                DefaultSyncStage(sync_command_list),
                DefaultRemoteInvokeStage(stack_name),
                DefaultStackOutputsStage(stack_outputs_command_list),
                DefaultDeleteStage(delete_command_list, stack_name),
            ]
            self._run_tests(stages)

    @staticmethod
    def _run_tests(stages: List[EndToEndBaseStage]):
        for stage in stages:
            command_result = stage.run_stage()
            stage.validate(command_result)

    def _get_init_command(self, temp_directory):
        return self.get_command(
            runtime=self.runtime,
            dependency_manager=self.dependency_manager,
            architecture="x86_64",
            app_template=self.app_template,
            name=self.app_name,
            no_interactive=True,
            output=temp_directory,
        )

    def _get_deploy_command(self, stack_name):
        self.stacks.append({"name": stack_name})
        return self.get_deploy_command_list(
            stack_name=stack_name,
            capabilities="CAPABILITY_IAM",
            confirm_changeset=False,
            force_upload=True,
            s3_bucket=self.s3_bucket.name,
        )

    def _get_delete_command(self, stack_name):
        return self.get_delete_command_list(stack_name=stack_name, region=self.region_name, no_prompts=True)

    def _get_stack_outputs_command(self, stack_name):
        return self.get_stack_outputs_command_list(stack_name=stack_name, output="json")

    def _get_sync_command(self, stack_name):
        self.stacks.append({"name": stack_name})
        return self.get_sync_command_list(stack_name=stack_name, template_file="template.yaml")


class EndToEndTestContext:
    def __init__(self, app_name):
        super().__init__()
        self.temporary_directory = TemporaryDirectory()
        self.app_name = app_name
        self.working_dir = ""
        self.template_path = ""

    def __enter__(self):
        temp = self.temporary_directory.__enter__()
        os.chdir(temp)
        self.template_path = str(Path(temp) / self.app_name / "template.yaml")
        self.working_dir = temp
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.temporary_directory.__exit__(exc_type, exc_val, exc_tb)
        os.chdir(Path(__file__).parent)
