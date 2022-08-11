import os
import time
import boto3
import re
from unittest import skipIf
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.list.endpoints.endpoints_integ_base import EndpointsIntegBase
from samcli.commands.list.endpoints.cli import HELP_TEXT
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input, method_to_stack_name

SKIP_endpoints_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_endpoints_TESTS, "Skip endpoints tests in CI/CD only")
class TestEndpoints(DeployIntegBase, EndpointsIntegBase):
    @classmethod
    def setUpClass(cls):
        DeployIntegBase.setUpClass()
        EndpointsIntegBase.setUpClass()

    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        time.sleep(CFN_SLEEP)
        super().setUp()

    def test_endpoints_help_message(self):
        cmdlist = self.get_endpoints_command_list(help=True)
        command_result = run_command(cmdlist)
        from_command = "".join(command_result.stdout.decode().split())
        from_help = "".join(HELP_TEXT.split())
        self.assertIn(from_help, from_command, "Endpoints help text should have been printed")

    def test_no_stack_name(self):
        template_path = self.list_test_data_path.joinpath("test_endpoints_template.yaml")
        region = boto3.Session().region_name
        cmdlist = self.get_endpoints_command_list(
            stack_name=None, output="json", region=region, template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = [
            """{
    "LogicalResourceId": "HelloWorldFunction",
    "PhysicalResourceId": "-",
    "CloudEndpoint": "-",
    "Methods": "-"
  }""",
            """{
    "LogicalResourceId": "TestAPI",
    "PhysicalResourceId": "-",
    "CloudEndpoint": "-",
    "Methods": []
  }""",
            """{
    "LogicalResourceId": "ServerlessRestApi",
    "PhysicalResourceId": "-",
    "CloudEndpoint": "-",
    "Methods": [
      "/hello2['get']",
      "/hello['get']"
    ]
  }""",
        ]
        for expression in expected_output:
            self.assertIn(expression, command_result.stdout.decode())

    def test_has_stack_name(self):
        template_path = self.list_test_data_path.joinpath("test_endpoints_template.yaml")
        stack_name = method_to_stack_name(self.id())
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
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        cmdlist = self.get_endpoints_command_list(
            stack_name=stack_name, output="json", region=region, template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = [
            """{
    "LogicalResourceId": "HelloWorldFunction",
    "PhysicalResourceId": "test-has-stack-name.*",
    "CloudEndpoint": "https://.*.lambda-url..*.on.aws/",
    "Methods": "-"
  }""",
            """  {
    "LogicalResourceId": "ServerlessRestApi",
    "PhysicalResourceId": ".*",
    "CloudEndpoint": .*
      "https://.*.execute-api..*.amazonaws.com/Prod",
      "https://.*.execute-api..*.amazonaws.com/Stage"
    .*,
    "Methods": .*
      "/hello2.'get'.",
      "/hello.'get'."
    .
  }""",
            """  {
    "LogicalResourceId": "TestAPI",
    "PhysicalResourceId": ".*",
    "CloudEndpoint": .
      "https://.*.execute-api..*.amazonaws.com/Test2"
    .,
    "Methods": ..
  }""",
        ]
        for expression in expected_output:
            self.assertTrue(re.search(expression, command_result.stdout.decode()))

    def test_stack_does_not_exist(self):
        template_path = self.list_test_data_path.joinpath("test_endpoints_template.yaml")
        stack_name = method_to_stack_name(self.id())
        config_file_name = stack_name + ".toml"
        region = boto3.Session().region_name
        cmdlist = self.get_endpoints_command_list(
            stack_name=stack_name, output="json", region=region, template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: The input stack {stack_name} does" f" not exist on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stderr.decode(), "Should have raised error that outputs do not exist"
        )
