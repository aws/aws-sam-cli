import os
import time
import boto3
import re
from unittest import skipIf
import click
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.list.stack_outputs.stack_outputs_integ_base import StackOutputsIntegBase
from samcli.commands.list.stack_outputs.cli import HELP_TEXT
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input, method_to_stack_name

SKIP_STACK_OUTPUTS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_STACK_OUTPUTS_TESTS, "Skip stack-outputs tests in CI/CD only")
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

    def test_stack_output_exists(self):
        template_path = self.list_test_data_path.joinpath("test_stack_creation_template.yaml")
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
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region, output="json")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertTrue(
            re.search(
                """{
    "OutputKey": "HelloWorldFunctionIamRole",
    "OutputValue": "arn:aws:iam::.*:role/.*-HelloWorldFunctionRole\-.*",
    "Description": "Implicit IAM Role created for Hello World function"
  }""",
                command_result.stdout.decode(),
            )
        )
        self.assertTrue(
            re.search(
                """  {
    "OutputKey": "HelloWorldApi",
    "OutputValue": "https://.*execute.*.amazonaws.com/Prod/hello/",
    "Description": "API Gateway endpoint URL for Prod stage for Hello World function"
  }""",
                command_result.stdout.decode(),
            )
        )
        self.assertTrue(
            re.search(
                """  {
    "OutputKey": "HelloWorldFunction",
    "OutputValue": "arn:aws:lambda:.*:.*:function:.*-HelloWorldFunction\-.*",
    "Description": "Hello World Lambda Function ARN"
  }""",
                command_result.stdout.decode(),
            )
        )

    def test_stack_no_outputs_exist(self):
        template_path = self.list_test_data_path.joinpath("test_stack_no_outputs_template.yaml")
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
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region, output="json")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: Outputs do not exist for the input stack {stack_name}" f" on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stderr.decode(), "Should have raised error that outputs do not exist"
        )

    def test_stack_does_not_exist(self):
        template_path = self.list_test_data_path.joinpath("test_stack_no_outputs_template.yaml")
        stack_name = method_to_stack_name(self.id())
        config_file_name = stack_name + ".toml"
        region = boto3.Session().region_name
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region, output="json")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: The input stack {stack_name} does" f" not exist on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stderr.decode(), "Should have raised error that outputs do not exist"
        )

    def test_stack_output_exists_table_output(self):
        template_path = self.list_test_data_path.joinpath("test_stack_creation_template.yaml")
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
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region)

        command_result = run_command(cmdlist, cwd=self.working_dir)
        header_string = "S\n*t\n*a\n*c\n*k\n*( )\n*O\n*u\n*t\n*p\n*u\n*t\n*s\n-+(-|\n)+O\n*u\n*t\n*p\n*u\n*t\n*K\n*e\n*y\n*( |\n)*O\n*u\n*t\n*p\n*u\n*t\n*V\n*a\n*l\n*u\n*e\n*( |\n)*D\n*e\n*s\n*c\n*r\n*i\n*p\n*t\n*i\n*o\n*n\n*( |\n)*-+(-|\n)+"
        expression_list = [
            "H\n*e\n*l\n*l\n*o\n*W\n*o\n*r\n*l\n*d\n*F\n*u\n*n\n*c\n*t\n*i\n*o\n*n\n*I\n*a\n*m\n*R\n*o\n*l\n*e\n*( |\n)*a\n*r\n*n\n*:\n*a\n*w\n*s\n*:\n*i\n*a\n*m\n*:\n*:\n*.*\n*:\n*r\n*o\n*l\n*e\n*.*( |\n)*I\n*m\n*p\n*l\n*i\n*c\n*i\n*t\n*( |\n)*I\n*A\n*M\n*( |\n)*R\n*o\n*l\n*e\n*( |\n)*c\n*r\n*e\n*a\n*t\n*e\n*d\n*( |\n)*f\n*o\n*r\n*",
            "H\n*e\n*l\n*l\n*o\n*W\n*o\n*r\n*l\n*d\n*A\n*p\n*i\n*( |\n)*h\n*t\n*t\n*p\n*s\n*:\n*/\n*/\n*.*\n*.\n*e\n*x\n*e\n*c\n*u\n*t\n*e\n*.*\n*( |\n)*A\n*P\n*I\n*( |\n)*G\n*a\n*t\n*e\n*w\n*a\n*y\n*( |\n)*e\n*n\n*d\n*p\n*o\n*i\n*n\n*t\n*( |\n)*U\n*R\n*L\n*( |\n)*f\n*o\n*r\n*",
            "H\n*e\n*l\n*l\n*o\n*W\n*o\n*r\n*l\n*d\n*F\n*u\n*n\n*c\n*t\n*i\n*o\n*n\n*( |\n)*a\n*r\n*n\n*:\n*a\n*w\n*s\n*:\n*l\n*a\n*m\n*b\n*d\n*a\n*:\n*.*\n*( |\n)*H\n*e\n*l\n*l\n*o\n*( |\n)*W\n*o\n*r\n*l\n*d\n*( |\n)*L\n*a\n*m\n*b\n*d\n*a\n*( |\n)*F\n*u\n*n\n*c\n*t\n*i\n*o\n*n\n*"
        ]
        self.assertTrue(
            re.search(
                header_string,
                command_result.stdout.decode(),
            )
        )
        for expression in expression_list:
            self.assertTrue(
                re.search(
                    expression,
                    command_result.stdout.decode(),
                )
            )
