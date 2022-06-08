import os
import time
import boto3
import re
from unittest import skipIf

from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.list.stack_outputs.stack_outputs_integ_base import StackOutputsIntegBase
from samcli.commands.list.stack_outputs.cli import HELP_TEXT
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input

SKIP_STACK_OUTPUTS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


class TestStackOutputs(DeployIntegBase, StackOutputsIntegBase):
    @classmethod
    def setUpClass(cls):
        DeployIntegBase.setUpClass()
        StackOutputsIntegBase.setUpClass()

    def setUp(self):

        self.cf_client = boto3.client("cloudformation")
        time.sleep(CFN_SLEEP)
        super().setUp()

    def test_stack_outputs_help_message(self):
        cmdlist = self.get_stack_outputs_command_list(help=True)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        from_command = "".join(command_result.stdout.decode().split())
        from_help = "".join(HELP_TEXT.split())
        self.assertIn(from_help, from_command, "Stack-outputs help text should have been printed")

    @skipIf(SKIP_STACK_OUTPUTS_TESTS, "Skip stack-outputs tests in CI/CD only")
    def test_stack_output_exists(self):
        template_path = self.list_test_data_path.joinpath("test_stack_creation_template.yaml")
        stack_name = self._method_to_stack_name(self.id())
        config_file_name = stack_name + ".toml"
        region = boto3.Session().region_name
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            guided=True,
            config_file=config_file_name,
            region=region,
            confirm_changeset=True,
            disable_rollback=True,
        )
        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertTrue(
            re.match(
                """^\[
  {
    "OutputKey": "HelloWorldFunctionIamRole",
    "OutputValue": "arn:aws:iam::............:role/test-stack-output-exists-0-HelloWorldFunctionRole\-............",
    "Description": "Implicit IAM Role created for Hello World function"
  },
  {
    "OutputKey": "HelloWorldApi",
    "OutputValue": "https://...........execute\-api.us\-east\-1.amazonaws.com/Prod/hello/",
    "Description": "API Gateway endpoint URL for Prod stage for Hello World function"
  },
  {
    "OutputKey": "HelloWorldFunction",
    "OutputValue": "arn:aws:lambda:us\-east\-1:............:function:test-stack-output-exists-0-0-0\-HelloWorldFunction\-............",
    "Description": "Hello World Lambda Function ARN"
  }
\]
""",
                command_result.stdout.decode(),
            )
        )

    @skipIf(SKIP_STACK_OUTPUTS_TESTS, "Skip stack-outputs tests in CI/CD only")
    def test_stack_no_outputs_exist(self):
        template_path = self.list_test_data_path.joinpath("test_stack_no_outputs_template.yaml")
        stack_name = self._method_to_stack_name(self.id())
        config_file_name = stack_name + ".toml"
        region = boto3.Session().region_name
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            guided=True,
            config_file=config_file_name,
            region=region,
            confirm_changeset=True,
            disable_rollback=True,
        )
        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: Outputs do not exist for the input stack {stack_name}" f" on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stdout.decode(), "Should have raised error that outputs do not exist"
        )

    @skipIf(SKIP_STACK_OUTPUTS_TESTS, "Skip stack-outputs tests in CI/CD only")
    def test_stack_does_not_exist(self):
        template_path = self.list_test_data_path.joinpath("test_stack_no_outputs_template.yaml")
        stack_name = self._method_to_stack_name(self.id())
        config_file_name = stack_name + ".toml"
        region = boto3.Session().region_name
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: The input stack {stack_name} does" f" not exist on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stdout.decode(), "Should have raised error that outputs do not exist"
        )

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"
