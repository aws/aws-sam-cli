import os

from typing import List

from samcli.cli.global_config import GlobalConfig
from tests.end_to_end.test_stages import EndToEndBaseStage
from tests.integration.delete.delete_integ_base import DeleteIntegBase
from tests.integration.init.test_init_base import InitIntegBase
from tests.integration.package.package_integ_base import PackageIntegBase
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.integration.remote.invoke.remote_invoke_integ_base import RemoteInvokeIntegBase
from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.integration.list.stack_outputs.stack_outputs_integ_base import StackOutputsIntegBase
import logging

LOG = logging.getLogger(__name__)


class EndToEndBase(InitIntegBase, StackOutputsIntegBase, DeleteIntegBase, SyncIntegBase):
    dependency_layer = True
    app_name = "sam-app"
    runtime = ""
    dependency_manager = ""
    app_template = ""

    def setUp(self):
        super().setUp()
        self.stacks = []
        self.config_file_dir = GlobalConfig().config_dir
        self._create_config_dir()

    def _create_config_dir(self):
        # Init tests will lock the config dir, ensure it exists before obtaining a lock
        if not self.config_file_dir.is_dir():
            os.mkdir(self.config_file_dir)

    @staticmethod
    def _run_tests(stages: List[EndToEndBaseStage]):
        for stage in stages:
            command_result = stage.run_stage()
            if command_result.stderr:
                LOG.info(str(command_result.stderr))
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

    def _get_package_command(self, s3_prefix, use_json=False, output_template_file=None):
        return PackageIntegBase.get_command_list(
            s3_bucket=self.s3_bucket.name,
            s3_prefix=s3_prefix,
            use_json=use_json,
            output_template_file=output_template_file,
        )

    def _get_local_command(self, function_name):
        return InvokeIntegBase.get_command_list(function_to_invoke=function_name)

    def _get_remote_invoke_command(self, stack_name, resource_id, event, output):
        return RemoteInvokeIntegBase.get_command_list(
            stack_name=stack_name, resource_id=resource_id, event=event, output=output
        )

    def _get_delete_command(self, stack_name):
        return self.get_delete_command_list(stack_name=stack_name, region=self.region_name, no_prompts=True)

    def _get_stack_outputs_command(self, stack_name):
        return self.get_stack_outputs_command_list(stack_name=stack_name, output="json")

    def _get_sync_command(self, stack_name):
        self.stacks.append({"name": stack_name})
        return self.get_sync_command_list(stack_name=stack_name, template_file="template.yaml")
