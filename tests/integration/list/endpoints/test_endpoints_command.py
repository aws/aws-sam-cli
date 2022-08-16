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

    def test_has_stack_name_table_output(self):
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
            stack_name=stack_name, region=region, template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        header_string = "-+(-|\n)+R\n*e\n*s\n*o\n*u\n*r\n*c\n*e\n*( |\n)*I\n*D\n*( |\n)*P\n*h\n*y\n*s\n*i\n*c\n*a\n*l\n*( |\n)*I\n*D\n*( |\n)*C\n*l\n*o\n*u\n*d\n*( |\n)*E\n*n\n*d\n*p\n*o\n*i\n*n\n*t\n*s\n*( |\n)*M\n*e\n*t\n*h\n*o\n*d\n*s\n*( |\n)*-+(-|\n)+"
        expression_list = [
            "H\n*e\n*l\n*l\n*o\n*W\n*o\n*r\n*l\n*d\n*F\n*u\n*n\n*c\n*t\n*i\n*o\n*n\n*( |\n)*t\n*e\n*s\n*t\n*.*( |\n)*h\n*t\n*t\n*p\n*s\n*:\n*/\n*/\n*.*( |\n)*-\n*( |\n)*",
            "S\n*e\n*r\n*v\n*e\n*r\n*l\n*e\n*s\n*s\n*R\n*e\n*s\n*t\n*A\n*p\n*i\n*( |\n)*.*( |\n)*h\n*t\n*t\n*p\n*s\n*:\n*/\n*/\n*.*( |\n)*/\n*h\n*e\n*l\n*l\n*o\n*2\n*.\n*.\n*g\n*e\n*t\n*.\n*.\n*;\n*( |\n)*",
            "T\n*e\n*s\n*t\n*A\n*P\n*I\n*( |\n)*.*( |\n)*h\n*t\n*t\n*p\n*s\n*:\n*/\n*/\n*.*( |\n)*-\n*( |\n)*"
        ]
        self.assertTrue(
            re.search(
                header_string,
                command_result.stdout.decode()
            )
        )

        for expression in expression_list:
            self.assertTrue(
                re.search(
                    expression,
                    command_result.stdout.decode()
                )
            )
