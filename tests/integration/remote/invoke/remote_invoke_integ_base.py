from unittest import TestCase, skipIf
from pathlib import Path
from typing import Optional

from tests.testing_utils import (
    get_sam_command,
    run_command,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
)
from tests.integration.deploy.deploy_integ_base import DeployIntegBase

from samcli.lib.utils.boto_utils import get_boto_resource_provider_with_config, get_boto_client_provider_with_config
from samcli.lib.utils.cloudformation import get_resource_summaries

SKIP_REMOTE_INVOKE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_REMOTE_INVOKE_TESTS, "Skip remote invoke tests in CI/CD only")
class RemoteInvokeIntegBase(TestCase):
    template: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        cls.cmd = get_sam_command()
        cls.test_data_path = cls.get_integ_dir().joinpath("testdata")
        if cls.template:
            cls.template_path = str(cls.test_data_path.joinpath("remote_invoke", cls.template))
        cls.events_folder_path = cls.test_data_path.joinpath("remote_invoke", "events")

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def remote_invoke_deploy_stack(stack_name, template_path):

        deploy_cmd = DeployIntegBase.get_deploy_command_list(
            stack_name=stack_name,
            template_file=template_path,
            resolve_s3=True,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
        )

        run_command(deploy_cmd)

    @classmethod
    def create_resources_and_boto_clients(cls):
        cls.remote_invoke_deploy_stack(cls.stack_name, cls.template_path)
        stack_resource_summaries = get_resource_summaries(
            get_boto_resource_provider_with_config(),
            get_boto_client_provider_with_config(),
            cls.stack_name,
        )
        cls.stack_resources = {
            resource_full_path: stack_resource_summary.physical_resource_id
            for resource_full_path, stack_resource_summary in stack_resource_summaries.items()
        }
        cls.cfn_client = get_boto_client_provider_with_config()("cloudformation")
        cls.lambda_client = get_boto_client_provider_with_config()("lambda")

    @staticmethod
    def get_command_list(
        stack_name=None,
        resource_id=None,
        event=None,
        event_file=None,
        parameter_list=None,
        output=None,
        region=None,
        profile=None,
        beta_features=None,
    ):
        command_list = [get_sam_command(), "remote", "invoke"]

        if stack_name:
            command_list = command_list + ["--stack-name", stack_name]

        if event:
            command_list = command_list + ["-e", event]

        if event_file:
            command_list = command_list + ["--event-file", event_file]

        if profile:
            command_list = command_list + ["--parameter", parameter]

        if output:
            command_list = command_list + ["--output", output]

        if parameter_list:
            for (parameter, value) in parameter_list:
                command_list = command_list + ["--parameter", f"{parameter}={value}"]

        if region:
            command_list = command_list + ["--region", region]

        if beta_features is not None:
            command_list = command_list + ["--beta-features" if beta_features else "--no-beta-features"]

        if resource_id:
            command_list = command_list + [resource_id]

        return command_list