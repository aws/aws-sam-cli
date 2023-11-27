from unittest import TestCase, skipIf
from pathlib import Path
from typing import Optional

from tests.testing_utils import (
    get_sam_command,
    run_command,
)
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from samcli.lib.remote_invoke.remote_invoke_executor_factory import RemoteInvokeExecutorFactory

from samcli.lib.utils.boto_utils import get_boto_resource_provider_with_config, get_boto_client_provider_with_config
from samcli.lib.utils.cloudformation import get_resource_summaries


class RemoteInvokeIntegBase(TestCase):
    template: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        cls.cmd = get_sam_command()
        cls.test_data_path = cls.get_integ_dir().joinpath("testdata")
        if cls.template:
            cls.template_path = str(cls.test_data_path.joinpath("remote_invoke", cls.template))
        cls.events_folder_path = cls.test_data_path.joinpath("remote_invoke", "events")

    @classmethod
    def tearDownClass(cls):
        # Delete the deployed stack
        cls.cfn_client.delete_stack(StackName=cls.stack_name)

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
        boto_client_provider = get_boto_client_provider_with_config()
        cls.stack_resource_summaries = get_resource_summaries(
            get_boto_resource_provider_with_config(),
            boto_client_provider,
            cls.stack_name,
        )
        cls.supported_resources = RemoteInvokeExecutorFactory.REMOTE_INVOKE_EXECUTOR_MAPPING.keys()
        cls.cfn_client = boto_client_provider("cloudformation")
        cls.lambda_client = boto_client_provider("lambda")
        cls.stepfunctions_client = boto_client_provider("stepfunctions")
        cls.xray_client = boto_client_provider("xray")
        cls.sqs_client = boto_client_provider("sqs")
        cls.kinesis_client = boto_client_provider("kinesis")

    def get_kinesis_records(self, shard_id, sequence_number, stream_name):
        """Helper function to get kinesis records using the provided shard_id and sequence_number

        Parameters
        ----------
        shard_id: string
            Shard Id to fetch the record from
        sequence_number: string
            Sequence number to get the record for
        stream_name: string
            Name of the kinesis stream to get records from
        Returns
        -------
        list
            Returns a list of records received from the kinesis data stream
        """
        response = self.kinesis_client.get_shard_iterator(
            StreamName=stream_name,
            ShardId=shard_id,
            ShardIteratorType="AT_SEQUENCE_NUMBER",
            StartingSequenceNumber=sequence_number,
        )
        shard_iter = response["ShardIterator"]
        response = self.kinesis_client.get_records(ShardIterator=shard_iter, Limit=1)
        records = response["Records"]

        return records

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
            for parameter, value in parameter_list:
                command_list = command_list + ["--parameter", f"{parameter}={value}"]

        if region:
            command_list = command_list + ["--region", region]

        if beta_features is not None:
            command_list = command_list + ["--beta-features" if beta_features else "--no-beta-features"]

        if resource_id:
            command_list = command_list + [resource_id]

        return command_list
