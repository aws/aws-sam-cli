from pathlib import Path

import logging
from typing import Optional, List
from unittest import TestCase

from samcli.lib.shared_test_events.lambda_shared_test_event import LAMBDA_TEST_EVENT_REGISTRY
from samcli.lib.utils.boto_utils import get_boto_resource_provider_with_config, get_boto_client_provider_with_config
from samcli.lib.utils.cloudformation import get_resource_summaries
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION
from tests.testing_utils import (
    get_sam_command,
    run_command,
)
from tests.integration.deploy.deploy_integ_base import DeployIntegBase


LOG = logging.getLogger(__name__)


class RemoteTestEventIntegBase(TestCase):
    template: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        cls.cmd = get_sam_command()
        cls.test_data_path = cls.get_integ_dir().joinpath("testdata")
        if cls.template:
            cls.template_path = str(cls.test_data_path.joinpath("remote_test_event", cls.template))
        cls.events_folder_path = cls.test_data_path.joinpath("remote_test_event", "events")

    @classmethod
    def tearDownClass(cls):
        # Delete remaining test events if there were not deleted during tests
        cls.delete_all_test_events()
        # Delete the deployed stack
        cls.cfn_client.delete_stack(StackName=cls.stack_name)
        cls.schemas_client.delete_registry(RegistryName=LAMBDA_TEST_EVENT_REGISTRY)

    @classmethod
    def create_resources_and_boto_clients(cls):
        cls.remote_invoke_deploy_stack(cls.stack_name, cls.template_path)
        boto_client_provider = get_boto_client_provider_with_config()
        cls.stack_resource_summaries = get_resource_summaries(
            get_boto_resource_provider_with_config(),
            boto_client_provider,
            cls.stack_name,
        )
        cls.lambda_client = boto_client_provider("lambda")
        cls.cfn_client = boto_client_provider("cloudformation")
        cls.schemas_client = boto_client_provider("schemas")

    @classmethod
    def delete_all_test_events(cls, logical_id=None):
        for _, resource in cls.stack_resource_summaries.items():
            if resource.resource_type == AWS_LAMBDA_FUNCTION:
                # If a logical id is passed, delete only that one
                if logical_id and logical_id != resource.logical_resource_id:
                    continue
                schema_name = f"_{resource.physical_resource_id}-schema"
                try:
                    cls.schemas_client.delete_schema(
                        RegistryName=LAMBDA_TEST_EVENT_REGISTRY,
                        SchemaName=schema_name,
                    )
                    LOG.info("Deleted lingering schema for test events: %s", schema_name)
                except Exception as e:  # Ignore if it doesn't exist (it was correctly deleted during tests)
                    LOG.debug("No events deleted (this is good) %s", e)
                    pass

    @staticmethod
    def get_command_list(
        subcommand,
        stack_name=None,
        resource_id=None,
        name=None,
        file=None,
        output_file=None,
        region=None,
        profile=None,
    ):
        command_list = [get_sam_command(), "remote", "test-event", subcommand]

        if stack_name:
            command_list += ["--stack-name", stack_name]

        if name:
            command_list += ["--name", name]

        if file:
            command_list += ["--file", file]

        if profile:
            command_list += ["--output_file", output_file]

        if region:
            command_list += ["--region", region]

        if resource_id:
            command_list += [resource_id]

        return command_list

    @staticmethod
    def get_remote_invoke_command_list(
        stack_name=None,
        resource_id=None,
        test_event_name=None,
        output=None,
    ):
        command_list = [get_sam_command(), "remote", "invoke"]

        if stack_name:
            command_list = command_list + ["--stack-name", stack_name]

        if test_event_name:
            command_list = command_list + ["--test-event-name", test_event_name]

        if output:
            command_list = command_list + ["--output", output]

        if resource_id:
            command_list = command_list + [resource_id]

        return command_list

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
